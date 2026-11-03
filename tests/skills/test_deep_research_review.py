"""Claim-level provenance and independent-model gate for grounded research."""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/research/grounded-citations/scripts/research.py"
spec = importlib.util.spec_from_file_location("actelyo_research", SCRIPT)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


@pytest.mark.parametrize("fault", ["invented_quote", "missing_verdict", "contradiction", "gap"])
def test_incomplete_or_unsupported_evidence_cannot_be_approved(fault):
    sources = {"1": {"id": "1", "url": "file:///bail.txt", "sha256": "fixture", "text": "Le dépôt est de 4817 euros."}}
    claims = [{"id": "c1", "text": "Le dépôt est de 4817 euros.",
               "passage_ids": list(research.build_catalog(sources))}]
    if fault == "invented_quote":
        claims[0]["quote"] = "Le dépôt est de 9999 euros."
    class Client:
        calls = []
        def complete(self, model, system, payload):
            if model == "writer":
                return {"claims": claims, "gaps": ["missing date"] if fault == "gap" else []}
            return {"decision": "approve", "claims": [] if fault == "missing_verdict" else [
                {"id": "c1", "verdict": "contradicted" if fault == "contradiction" else "supported"}]}
    if fault == "missing_verdict":
        with pytest.raises(ValueError, match="every claim"):
            research.run("Dépôt ?", sources, "writer", "judge", Client())
    else:
        assert research.run("Dépôt ?", sources, "writer", "judge", Client())["status"] == "research_again"


def test_real_http_transport_preserves_models_quotes_and_usage(tmp_path):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body)
            input_data = json.loads(body["messages"][1]["content"])
            payload = ({"claims": [{"id": "c1", "text": "La somme est de 4817 euros.",
                       "passage_ids": [input_data["passages"][0]["passage_id"]]}], "gaps": []}
                       if body["model"] == "writer" else {"decision": "approve", "claims": [
                           {"id": "c1", "verdict": "supported", "reason": "matches evidence"}]})
            reply = json.dumps({"model": body["model"], "choices": [{"message": {"content": json.dumps(payload)}}],
                                "usage": {"prompt_tokens": 41, "completion_tokens": 20}}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source_file = tmp_path / "sources.json"
        source_file.write_text(json.dumps([{"id": "1", "url": "file:///bail.txt", "text": "Dépôt : 4817 euros."}]))
        client = research.ModelClient(f"http://127.0.0.1:{server.server_port}/v1")
        result = research.run("Dépôt ?", research.load_sources(source_file), "writer", "judge", client)
        assert result["status"] == "approved"
        assert [call["model"] for call in calls] == ["writer", "judge"]
        selection = calls[0]["response_format"]["json_schema"]["schema"]["properties"]["claims"]["items"]["properties"]["passage_ids"]["items"]["enum"]
        assert set(selection) == {p["passage_id"] for p in result["passages"]}
        assert len(result["sources"][0]["sha256"]) == 64
        assert all(call["usage"]["prompt_tokens"] == 41 for call in result["calls"])
        assert result["claims"][0]["evidence"][0]["quote"] == "Dépôt : 4817 euros."
        assert "Sources" in research.render_report(result)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
