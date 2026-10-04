import json
import tempfile
import unittest
from pathlib import Path

from law_harness.harness import Harness
from law_harness.core import load_config
from law_harness.server import make_http_server, connection_manifest


class ConnectionTests(unittest.TestCase):
    def test_connection_manifest_tracks_actual_listening_port_and_private_token(self):
        cfg = load_config(Path(__file__).resolve().parents[1] / "config.example.toml")
        token = "synthetic-private-token-at-least-32-characters"
        server = make_http_server(Harness(cfg), 0, token)
        try:
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder) / "connection.json"
                connection_manifest(server, token, target)
                manifest = json.loads(target.read_text())
                self.assertEqual(manifest["endpoint"], f"http://127.0.0.1:{server.server_port}")
                self.assertEqual(manifest["token"], token)
                self.assertEqual(list(Path(folder).iterdir()), [target])
                self.assertNotIn("token", Harness(cfg).doctor())
        finally:
            server.server_close()
