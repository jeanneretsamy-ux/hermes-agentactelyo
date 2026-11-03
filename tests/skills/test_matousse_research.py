"""System One wire contract; these tests do not load Matousse model weights."""
import importlib.util
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

script = Path(__file__).resolve().parents[2] / "skills/research/grounded-citations/scripts/research.py"
spec = importlib.util.spec_from_file_location("matousse_research", script)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


@pytest.mark.parametrize("mode", ["supported", "uncertain", "wrong_checkpoint", "truncated"])
def test_systemone_identity_and_abstention_over_real_http(mode):
    calls = []
    expected = research.MatousseClient.REPOSITORY + "@" + research.MatousseClient.REVISION
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, value):
            body = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            self.reply({"models": [{"run": "other/model" if mode == "wrong_checkpoint" else expected}]})
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, body))
            confidence = 0.6 if mode == "uncertain" else 0.999
            self.reply({"answers": {"claim_0": {"choice": "supported", "probabilities": {
                "supported": confidence, "unsupported": 1-confidence, "contradicted": 0}},
                "complete": {"noul": 0.999}}, "truncated": mode == "truncated", "usage": {"input_tokens": 90}})
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = research.MatousseClient(f"http://127.0.0.1:{server.server_port}/v1", experimental=True)
        payload = {"question": "Montant ?", "claims": [{"id": "c1", "text": "4817 euros"}]}
        if mode in ("wrong_checkpoint", "truncated"):
            with pytest.raises(ValueError, match="checkpoint|truncated"):
                client.complete(client.REPOSITORY, "", payload)
        else:
            result = client.complete(client.REPOSITORY, "", payload)
            assert result["decision"] == ("approve" if mode == "supported" else "research_again")
            path, request = calls[0]
            assert path == "/v1/systemone"
            assert request["questions"]["claim_0"]["type"] == "choice"
            assert request["state"] == payload
            assert client.calls[0]["experimental"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_unpromoted_candidate_requires_explicit_evaluation_mode():
    with pytest.raises(ValueError, match="not promoted"):
        research.MatousseClient("http://127.0.0.1:8009/v1")
    class ExperimentalPipeline:
        calls = [{"experimental": True}]
        def complete(self, model, system, payload):
            if model == "writer":
                return {"claims": [{"id": "c1", "text": "4817 euros", "evidence": [
                    {"source_id": "1", "quote": "4817 euros"}]}], "gaps": []}
            return {"decision": "approve", "claims": [{"id": "c1", "verdict": "supported"}]}
    source = {"1": {"id": "1", "text": "4817 euros", "url": "file:///bail", "sha256": "fixture"}}
    result = research.run("Montant ?", source, "writer", "judge", ExperimentalPipeline())
    assert result["status"] == "experimental_review_passed"
    assert result["requires_human_review"] is True
    assert result["candidate_promoted"] is False
