from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import HarnessError, load_config
from .harness import Harness
from .server import serve_http, serve_mcp


def main():
    # MCP mandates UTF-8; Windows terminals may otherwise use a legacy code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Actelyo Law Harness — revue contractuelle sourcée")
    parser.add_argument("--config", default="config.toml")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--probe-model", action="store_true")
    review = commands.add_parser("review")
    review.add_argument("request_file")
    review.add_argument("--output", help="Écriture permise uniquement si toutes les preuves autorisent la conservation")
    http = commands.add_parser("serve")
    http.add_argument("--port", type=int, default=8765)
    http.add_argument("--connection-file", help="Fichier de connexion privé à sélectionner dans Actelyo ERP")
    commands.add_parser("mcp")
    args = parser.parse_args()
    try:
        harness = Harness(load_config(args.config))
        if args.command == "doctor":
            print(json.dumps(harness.doctor(args.probe_model), ensure_ascii=False, indent=2))
        elif args.command == "review":
            request = json.loads(Path(args.request_file).read_text(encoding="utf-8-sig"))
            result = harness.review(request)
            serialized = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output:
                harness.authorize_persistence(result)
                # Avoid accidentally replacing an existing review or user document.
                with open(args.output, "x", encoding="utf-8") as handle:
                    handle.write(serialized + "\n")
            else:
                print(serialized)
            return 2 if result["status"] in {"insufficient_evidence", "blocked_validation"} else 0
        elif args.command == "serve":
            serve_http(harness, args.port, args.connection_file)
        elif args.command == "mcp":
            serve_mcp(harness)
    except (HarnessError, OSError, ValueError) as exc:
        message = str(exc) if isinstance(exc, HarnessError) else "Fichier/configuration/port invalide ou inaccessible"
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0
