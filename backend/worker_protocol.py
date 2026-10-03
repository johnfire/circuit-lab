"""Size-bounded JSON framing over a local Unix socket, without network access."""

import json
import socket
import struct

MAX_REQUEST_BYTES = 8192
MAX_RESPONSE_BYTES = 4_000_000


def receive_exact(connection: socket.socket, length: int) -> bytes:
    """Read a complete frame or reject a closed/truncated connection."""
    fragments = bytearray()
    while len(fragments) < length:
        fragment = connection.recv(length - len(fragments))
        if not fragment:
            raise ValueError("Worker connection closed before its response completed")
        fragments.extend(fragment)
    return bytes(fragments)


def receive_frame(connection: socket.socket, maximum: int) -> dict[str, object]:
    """Bound the length before allocating or parsing a JSON object."""
    length = struct.unpack("!I", receive_exact(connection, 4))[0]
    if not 0 < length <= maximum:
        raise ValueError("Worker message exceeds its size limit")
    payload: object = json.loads(receive_exact(connection, length))
    if not isinstance(payload, dict):
        raise ValueError("Worker message must be an object")
    return payload


def send_frame(connection: socket.socket, payload: dict[str, object]) -> None:
    """Send one bounded response without assuming socket writes are complete."""
    encoded = json.dumps(payload, allow_nan=False).encode()
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise ValueError("Worker response exceeds its size limit")
    connection.sendall(struct.pack("!I", len(encoded)) + encoded)


def exchange_frame(socket_path: str, payload: dict[str, object]) -> dict[str, object]:
    """Connect to the configured local worker with an independent deadline."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(18)
        connection.connect(socket_path)
        send_frame(connection, payload)
        return receive_frame(connection, MAX_RESPONSE_BYTES)
