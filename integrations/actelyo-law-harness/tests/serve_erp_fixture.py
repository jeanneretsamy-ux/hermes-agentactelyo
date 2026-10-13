"""Synthetic providers, real server and real pipeline for the ERP bridge E2E test."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_harness import FakeModel, FakeConnector, config
from law_harness.harness import Harness
from law_harness.server import connection_manifest, make_http_server

if __name__ == "__main__":
    token = "synthetic-erp-fixture-token-at-least-32-characters"
    server = make_http_server(Harness(config(), model=FakeModel(),
                                     connectors={"legifrance": FakeConnector()}), 0, token)
    connection_manifest(server, token, sys.argv[1])
    server.serve_forever()
