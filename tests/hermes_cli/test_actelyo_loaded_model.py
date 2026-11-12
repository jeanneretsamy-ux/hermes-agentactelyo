"""Actual loopback HTTP discovery and profile reads; no model inference."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from hermes_cli.runtime_provider import _get_model_config
from hermes_constants import set_hermes_home_override, reset_hermes_home_override


@contextmanager
def catalog_server():
    state = {"catalog": {}, "requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"].append(self.path)
            assert self.path == "/v1/models"
            body = json.dumps(state["catalog"]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", state
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_actual_profile_discovers_only_loaded_language_model_and_preserves_explicit_choice(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    token = set_hermes_home_override(tmp_path)
    try:
        with catalog_server() as (url, state):
            path = tmp_path / "config.yaml"
            path.write_text(f'model:\n  provider: custom\n  base_url: {url}\n  default: ""\n', encoding="utf-8")
            original = path.read_bytes()
            state["catalog"] = {"actelyo_llm": True, "data": [
                {"id": "fixture-embed", "type": "embeddings", "state": "loaded"},
                {"id": "fixture-not-loaded", "type": "llm", "state": "not-loaded"},
                {"id": "fixture-active", "type": "llm", "state": "loaded"},
            ]}
            resolved = _get_model_config()
            assert resolved["default"] == "fixture-active" and resolved["base_url"] == url
            assert path.read_bytes() == original and state["requests"] == ["/v1/models"]
            path.write_text(original.decode().replace('default: ""', 'default: "personal-choice"'), encoding="utf-8")
            assert _get_model_config()["default"] == "personal-choice"
            assert state["requests"] == ["/v1/models"]
    finally:
        reset_hermes_home_override(token)


def test_real_catalog_refuses_unloaded_or_ambiguous_actelyo_and_preserves_generic_discovery(tmp_path, monkeypatch):
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    token = set_hermes_home_override(tmp_path)
    try:
        with catalog_server() as (url, state):
            (tmp_path / "config.yaml").write_text(
                f'model:\n  provider: custom\n  base_url: {url}\n  default: ""\n', encoding="utf-8")
            for rows in ([{"id": "embedding", "type": "embeddings", "state": "loaded"}],
                         [{"id": "loading", "type": "llm", "state": "loading"}],
                         [{"id": name, "type": "llm", "state": "loaded"} for name in ("one", "two")]):
                state["catalog"] = {"actelyo_llm": True, "data": rows}
                assert _get_model_config()["default"] == ""
            state["catalog"] = {"data": [{"id": "generic-single-model"}]}
            assert _get_model_config()["default"] == "generic-single-model"
    finally:
        reset_hermes_home_override(token)
