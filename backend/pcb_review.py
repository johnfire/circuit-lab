"""Authenticated, bounded bridge to the independently isolated KiCad worker."""
import base64
import dataclasses
import os
import socket
import struct
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from backend.audit_log import record_action
from backend.kicad_export import components_for, net_names
from backend.model_primitives import StrictModel
from backend.schematic_models import SchematicRequest
from backend.schematic_topology import assign_nodes
from backend.worker_protocol import receive_frame, send_frame

router = APIRouter()
MAX_BOARD_BYTES = 1_048_576
MAX_WORKER_RESPONSE = 12_000_000


class DraftRequest(StrictModel):
    circuit: SchematicRequest
    width_mm: float = Field(ge=20, le=300, allow_inf_nan=False)
    height_mm: float = Field(ge=20, le=300, allow_inf_nan=False)


def request_board(job: dict[str, Any]) -> dict[str, Any]:
    """Use only a configured IPC socket; never process uploaded boards in the API."""
    path = os.environ.get('CIRCUIT_PCB_SOCKET', '')
    if not path:
        raise HTTPException(503, 'PCB review service unavailable')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(45)
            connection.connect(path)
            send_frame(connection, job)
            response = receive_frame(connection, MAX_WORKER_RESPONSE)
    except (OSError, ValueError, struct.error) as error:
        raise HTTPException(503, 'PCB review service unavailable') from error
    if 'error' in response:
        raise HTTPException(422, 'Board could not be processed')
    return response


@router.post('/api/pcb/generate')
def generate_board(submitted: DraftRequest, request: Request) -> dict[str, Any]:
    try:
        nodes = assign_nodes(submitted.circuit)
        parts, warnings = components_for(submitted.circuit, nodes)
        if any(part.board_pin and part.board_pin.board in {'raspberry_pi_4', 'raspberry_pi_5'}
               for part in submitted.circuit.parts):
            raise ValueError('Pi HAT requires a verified template')
        job = {'operation': 'generate', 'width_mm': submitted.width_mm, 'height_mm': submitted.height_mm,
               'parts': [dataclasses.asdict(part) for part in parts], 'nets': net_names(submitted.circuit, nodes)}
        record_action("pcb.generate", "draft", request.state.correlation_id, "started", request.state.actor, "pcb")
        try:
            result = request_board(job)
        except HTTPException:
            record_action("pcb.generate", "draft", request.state.correlation_id, "error", request.state.actor, "pcb")
            raise
        record_action("pcb.generate", "draft", request.state.correlation_id, "completed", request.state.actor, "pcb")
        return {**result, 'origin': 'generated', 'warnings': [*warnings, *result.get('warnings', [])]}
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.post('/api/pcb/review')
async def review_board(request: Request) -> dict[str, Any]:
    length = request.headers.get('content-length')
    if length and length.isdigit() and int(length) > MAX_BOARD_BYTES:
        raise HTTPException(413, 'Board exceeds the size limit')
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > MAX_BOARD_BYTES:
            raise HTTPException(413, 'Board exceeds the size limit')
    try:
        board = bytes(buffer).decode('utf-8')
    except UnicodeDecodeError as error:
        raise HTTPException(422, 'Expected a UTF-8 KiCad board') from error
    if not board.lstrip().startswith('(kicad_pcb'):
        raise HTTPException(422, 'Expected a KiCad board')
    record_action('pcb.review', 'import', request.state.correlation_id, 'started', request.state.actor, 'pcb')
    try:
        result = await run_in_threadpool(request_board, {'operation': 'review', 'board': base64.b64encode(buffer).decode('ascii')})
    except HTTPException:
        record_action('pcb.review', 'import', request.state.correlation_id, 'error', request.state.actor, 'pcb')
        raise
    record_action('pcb.review', 'import', request.state.correlation_id, 'completed', request.state.actor, 'pcb')
    return {**result, 'origin': 'imported'}
