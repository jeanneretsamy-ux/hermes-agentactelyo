"""Exercise the cabinet helper over real local HTTP, with synthetic receipts."""
import importlib.util
import json
from pathlib import Path
import threading
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture
def cabinet():
    path = Path(__file__).resolve().parents[2] / "skills/productivity/actelyo-applications/scripts/cabinet_link.py"
    spec = importlib.util.spec_from_file_location("actelyo_cabinet_link", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_http_authentication_receipt_and_cancellation(cabinet, tmp_path, capsys):
    token, calls = "a" * 64, []
    state = {"cancelled": False, "available": True, "redirect": False}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.headers["Authorization"] == "Bearer " + token
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"product": "Actelyo ERP", "native_cabinet": {"version": 1} if state["available"] else None, "pendingApprovals": [{"detail": "private"}]}).encode())

        def do_POST(self):
            assert self.path == "/cabinet"
            assert self.headers["Authorization"] == "Bearer " + token
            if state["redirect"]:
                self.send_response(302)
                self.send_header("Location", "http://example.invalid/never-follow")
                self.end_headers()
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body)
            self.send_response(200)
            self.end_headers()
            result = {"cancelled": True} if state["cancelled"] else {"content": [{"type": "text", "text": json.dumps({"id": "native-object", "status": "draft", "label": "Réunion 😀"})}]}
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bridge = tmp_path / "bridge.json"
    bridge.write_text(json.dumps({"endpoint": f"http://127.0.0.1:{server.server_port}", "token": token}))
    try:
        client = cabinet.CabinetClient(bridge)
        assert "pendingApprovals" not in client.status()
        result = client.call("snapshot", {}, "observed-dossier")
        assert result["confirmed"] and result["result"]["id"] == "native-object"
        assert calls[-1]["dossierId"] == "observed-dossier"
        input_file = tmp_path / "input.json"
        input_file.write_text("{}")
        piped = subprocess.run([sys.executable, cabinet.__file__, "--bridge", str(bridge),
            "call", "snapshot", "--input-file", str(input_file), "--dossier", "observed-dossier"],
            env={**os.environ,"PYTHONIOENCODING":"cp1252"}, capture_output=True, encoding="ascii", timeout=10)
        assert piped.returncode == 0, piped.stderr
        assert json.loads(piped.stdout)["result"]["label"] == "Réunion 😀"
        assert token not in piped.stdout
        successful_calls = len(calls)
        state["cancelled"] = True
        input_file = tmp_path / "input.json"
        input_file.write_text("{}")
        assert cabinet.main(["--bridge", str(bridge), "call", "snapshot", "--input-file", str(input_file)]) == 3
        output = capsys.readouterr().out
        assert token not in output and json.loads(output)["confirmed"] is False
        assert len(calls) == successful_calls + 1
        state["available"] = False
        with pytest.raises(ValueError, match="update"):
            client.status()
        state["available"], state["redirect"] = True, True
        with pytest.raises(ValueError, match="redirect"):
            client.call("snapshot", {})
        assert len(calls) == successful_calls + 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("endpoint", ["http://example.invalid:1234", "http://localhost:1234", "http://127.0.0.1:1234/other", "http://user:password@127.0.0.1:1234", "http://127.0.0.1:1234?x=1"])
def test_refuses_non_loopback_and_credential_endpoints(cabinet, tmp_path, endpoint):
    bridge = tmp_path / "bridge.json"
    bridge.write_text(json.dumps({"endpoint": endpoint, "token": "b" * 64}))
    with pytest.raises(ValueError):
        cabinet.CabinetClient(bridge)
