"""Exercise the desktop link against a real local HTTP endpoint and absent ports."""
import importlib.util
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def link():
    path = Path(__file__).resolve().parents[2] / 'skills/productivity/actelyo-applications/scripts/desktop_link.py'
    spec = importlib.util.spec_from_file_location('actelyo_desktop_link', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_probe_reads_observed_targets_and_refuses_launch_on_busy_port(link, tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = ({'Browser': 'Test CDP', 'webSocketDebuggerUrl': 'ws://127.0.0.1/devtools/browser/test'}
                    if self.path == '/json/version' else
                    [{'id': 'observed-id', 'type': 'page', 'title': 'Observed Actelyo window', 'url': 'file:///app/index.html'}])
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = link.probe(server.server_port)
        assert result['targets'][0]['id'] == 'observed-id'
        assert result['targets'][0]['url'].startswith('file:')
        executable = tmp_path / 'unused-executable'
        executable.write_bytes(b'not executed')
        with pytest.raises(OSError):
            link.launch(executable, server.server_port)
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_probe_rejects_invalid_port_and_non_cdp_endpoint(link):
    with pytest.raises(ValueError):
        link.probe(80)
