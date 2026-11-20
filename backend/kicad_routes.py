"""Browser API for PCB export: KiCad files from the wiring, and a bring-up sheet from a fresh simulation."""

from pathlib import Path
from typing import Literal, cast

from fastapi import APIRouter, Request

from backend.audit_log import record_simulation
from backend.bring_up_sheet import bring_up_sheet
from backend.kicad_export import export_kicad
from backend.localization import LocalizationMetadata
from backend.localized_http import http_failure
from backend.model_primitives import StrictModel
from backend.schematic_engine import compile_schematic
from backend.schematic_models import SchematicRequest
from backend.simulation_engine import SimulationFailure
from backend.worker_gateway import launch_schematic

router = APIRouter()


class KicadFiles(StrictModel, LocalizationMetadata):
    """The files to download and what the user still needs to do."""

    netlist: str
    bom_csv: str
    design_rules: str
    fab_guide: str
    warnings: list[str]


@router.post("/api/export/kicad", response_model=KicadFiles)
def export_for_pcb(submitted: SchematicRequest, language: Literal["de", "en"] = "en") -> KicadFiles:
    """No simulation runs; the circuit must just be completely and validly wired."""
    try:
        exported = export_kicad(submitted)
    except ValueError as error:
        raise http_failure(422, error, "Not ready for PCB export: ") from error
    return KicadFiles(netlist=exported.netlist, bom_csv=exported.bom_csv, design_rules=exported.design_rules,
                      fab_guide=((Path(__file__).resolve().parents[1] / "circuits/pcb/fab-guide.de.md").read_text()
                                 if language == "de" else exported.fab_guide), warnings=exported.warnings)


class BringUpSheet(StrictModel):
    """A markdown checklist for powering up the built board."""

    sheet: str


@router.post("/api/export/bring-up", response_model=BringUpSheet)
def export_bring_up(submitted: SchematicRequest, request: Request, language: Literal["de", "en"] = "en") -> BringUpSheet:
    """Simulate in the isolated worker, audited like any run; a worker outage fails only this file."""
    correlation_id = cast(str, request.state.correlation_id)
    actor = cast(str, request.state.actor)
    try:
        compile_schematic(submitted)
    except ValueError as error:
        raise http_failure(422, error, "Not ready for a bring-up sheet: ") from error
    try:
        record_simulation("bring_up", correlation_id, "started", actor)
        report = launch_schematic(submitted, correlation_id)
        record_simulation("bring_up", correlation_id, report.status, actor)
    except SimulationFailure as error:
        try:
            record_simulation("bring_up", correlation_id, "error", actor)
        except SimulationFailure:
            pass  # The audit writer already records its own storage failure.
        raise http_failure(503, error) from error
    return BringUpSheet(sheet=bring_up_sheet(submitted, report, language))
