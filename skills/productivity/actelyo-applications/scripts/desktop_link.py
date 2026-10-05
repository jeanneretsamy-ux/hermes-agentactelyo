"""Launch an explicitly selected Electron app and inspect its loopback CDP targets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.request import ProxyHandler, build_opener


def read_endpoint(port: int, route: str):
    if not 1024 <= port <= 65535:
        raise ValueError('Choose a port between 1024 and 65535.')
    opener = build_opener(ProxyHandler({}))
    with opener.open(f'http://127.0.0.1:{port}/{route}', timeout=3) as response:
        return json.load(response)


def probe(port: int) -> dict:
    version = read_endpoint(port, 'json/version')
    if not version.get('webSocketDebuggerUrl'):
        raise ValueError('The endpoint is not a Chromium CDP browser.')
    targets = read_endpoint(port, 'json/list')
    pages = [{'id': p['id'], 'title': p.get('title', ''), 'url': p.get('url', '')}
             for p in targets if p.get('type') == 'page']
    return {'endpoint': f'http://127.0.0.1:{port}', 'browser': version.get('Browser'),
            'targets': pages, 'status': 'connected' if pages else 'no_window_yet'}


def launch(executable: Path, port: int) -> dict:
    executable = executable.expanduser().resolve(strict=True)
    if not executable.is_file():
        raise ValueError('The executable must be an existing file.')
    # Refuse a port already in use rather than attaching to a different application.
    import socket
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', port))
    process = subprocess.Popen([str(executable), '--remote-debugging-address=127.0.0.1',
                                f'--remote-debugging-port={port}'], cwd=executable.parent)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            result = probe(port)
            return {'launched_pid': process.pid, 'executable': str(executable), **result}
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError('CDP did not start. An existing single-instance application may have ignored the flags. Save work, fully exit that app and retry; no processes were killed.')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('launch', 'probe'):
        p = sub.add_parser(command)
        p.add_argument('--port', type=int, default=9229)
        if command == 'launch':
            p.add_argument('--executable', type=Path, required=True)
    args = parser.parse_args()
    try:
        if not 1024 <= args.port <= 65535:
            raise ValueError('Choose a port between 1024 and 65535.')
        result = launch(args.executable, args.port) if args.command == 'launch' else probe(args.port)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
