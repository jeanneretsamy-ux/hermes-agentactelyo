import importlib.util
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


@pytest.fixture
def bridge():
    path = Path(__file__).resolve().parents[2] / "mcp-servers/actelyo-rag/actelyo_rag_mcp.py"
    spec = importlib.util.spec_from_file_location("actelyo_rag_bridge_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def backend():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.path == "/api/v1/workspaces"
            assert self.headers["Authorization"] == "Bearer fixture-key"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"port": self.server.server_port}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_mcp_request_follows_desktop_port_changes(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(bridge, "API_BASE", "")
    monkeypatch.setattr(bridge, "API_KEY", "fixture-key")
    log = tmp_path / "Actelyo RAG" / "desktop.log"
    log.parent.mkdir()
    with backend() as first, backend() as second:
        for port in (first, second):
            with log.open("a", encoding="utf-8") as stream:
                stream.write(f"[backend] info: Primary server in HTTP mode listening on port {port}\n")
            result = bridge.handle({"method": "tools/call", "params": {
                "name": "actelyo_rag_list_workspaces", "arguments": {}}})
            assert json.loads(result["content"][0]["text"])["port"] == port


def test_explicit_endpoint_takes_priority(bridge, monkeypatch):
    monkeypatch.setattr(bridge, "API_BASE", "https://rag.example/api")
    assert bridge.api_base() == "https://rag.example/api"


def test_missing_desktop_service_does_not_guess_a_port(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(bridge, "API_BASE", "")
    with pytest.raises(RuntimeError, match='not detected'):
        bridge.api_base()


def test_service_announcement_follows_restart_and_stopped_state(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    monkeypatch.setattr(bridge, 'API_BASE', '')
    monkeypatch.setattr(bridge, 'API_KEY', 'fixture-key')
    receipt = tmp_path / 'Actelyo RAG' / 'desktop-service.json'
    receipt.parent.mkdir()
    with backend() as first, backend() as second:
        for port in (first, second):
            receipt.write_text(json.dumps({'schemaVersion': 1, 'product': 'Actelyo RAG', 'pid': 1234, 'state': 'ready', 'apiBase': f'http://127.0.0.1:{port}/api/v1'}))
            result = bridge.list_workspaces({})
            assert json.loads(result['content'][0]['text'])['port'] == port
    receipt.write_text(json.dumps({'schemaVersion': 1, 'product': 'Actelyo RAG', 'pid': 1234, 'state': 'stopped', 'apiBase': 'http://127.0.0.1:1234/api/v1'}))
    with pytest.raises(RuntimeError, match='stopped'):
        bridge.api_base()


def test_invalid_announcement_does_not_fall_back_to_a_stale_log(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    monkeypatch.setattr(bridge, 'API_BASE', '')
    directory = tmp_path / 'Actelyo RAG'
    directory.mkdir()
    (directory / 'desktop.log').write_text('Primary server in HTTP mode listening on port 12345\n')
    (directory / 'desktop-service.json').write_text(json.dumps({'schemaVersion': 1, 'product': 'other', 'pid': 1, 'apiBase': 'https://example.invalid/api/v1'}))
    with pytest.raises(RuntimeError, match='Invalid'):
        bridge.api_base()
