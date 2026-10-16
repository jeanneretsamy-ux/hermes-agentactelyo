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


def test_missing_desktop_log_retains_legacy_endpoint(bridge, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(bridge, "API_BASE", "")
    assert bridge.api_base() == "http://127.0.0.1:61045/api"
