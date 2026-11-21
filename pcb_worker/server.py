"""Small bounded Unix socket server for isolated KiCad processes."""
import json
import os
import struct
from pathlib import Path
from socketserver import BaseRequestHandler, UnixStreamServer

from pcb_worker.process import process

LIMIT = 2_000_000


def read_exact(connection, count):
    result = bytearray()
    while len(result) < count:
        chunk = connection.recv(count - len(result))
        if not chunk:
            raise ValueError('Incomplete request')
        result.extend(chunk)
    return bytes(result)


class Handler(BaseRequestHandler):
    def handle(self):
        self.request.settimeout(45)
        try:
            size = struct.unpack('!I', read_exact(self.request, 4))[0]
            if not 0 < size <= LIMIT:
                raise ValueError('Request too large')
            job = json.loads(read_exact(self.request, size))
            result = {'status': 'ok'} if job == {'operation': 'health'} else process(job)
        except Exception:
            result = {'error': 'Board processing failed'}
        encoded = json.dumps(result).encode()
        if len(encoded) > 12_000_000:
            encoded = b'{"error":"Board output too large"}'
        self.request.sendall(struct.pack('!I', len(encoded)) + encoded)


def main():
    path = Path(os.environ.get('CIRCUIT_PCB_LISTEN', '/run/circuit-pcb/pcb.sock'))
    if path.exists():
        if not path.is_socket():
            raise ValueError('PCB socket path is not a socket')
        path.unlink()
    os.umask(0o007)
    with UnixStreamServer(str(path), Handler) as server:
        path.chmod(0o660)
        server.serve_forever()


if __name__ == '__main__':
    main()
