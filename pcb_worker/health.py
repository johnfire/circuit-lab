"""Check that the private PCB worker accepts and answers a framed request."""
import json
import os
import socket
import struct


def main():
    payload = json.dumps({'operation': 'health'}).encode()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(3)
        connection.connect(os.environ.get('CIRCUIT_PCB_LISTEN', '/run/circuit-pcb/pcb.sock'))
        connection.sendall(struct.pack('!I', len(payload)) + payload)
        header = connection.recv(4, socket.MSG_WAITALL)
        length = struct.unpack('!I', header)[0]
        if length > 128 or json.loads(connection.recv(length, socket.MSG_WAITALL)) != {'status': 'ok'}:
            raise ValueError('PCB worker health check failed')


if __name__ == '__main__':
    main()
