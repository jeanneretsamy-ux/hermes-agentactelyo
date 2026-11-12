"""Call the authenticated, approval-gated Actelyo cabinet on this computer."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CabinetClient:
    def __init__(self, bridge_file: Path):
        if bridge_file.stat().st_size > 4096:
            raise ValueError("Bridge configuration too large.")
        config = json.loads(bridge_file.read_text(encoding="utf-8-sig"))
        endpoint = config.get("endpoint", "")
        parsed = urlsplit(endpoint)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
                or not parsed.port or not 1024 <= parsed.port <= 65535
                or parsed.username or parsed.password or parsed.path
                or parsed.query or parsed.fragment
                or parsed.netloc != f"127.0.0.1:{parsed.port}"):
            raise ValueError("Expected the ERP's exact loopback endpoint.")
        token = config.get("token", "")
        if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token):
            raise ValueError("Invalid local bridge credential.")
        self.endpoint, self._token = endpoint, token
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def _request(self, route: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if data is not None and len(data) > 100000:
            raise ValueError("Command exceeds the cabinet's 100 kB limit.")
        request = Request(self.endpoint + route, data=data, headers={
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json",
        })
        try:
            with self.opener.open(request, timeout=240) as response:
                body = response.read(4 * 1024 * 1024 + 1)
        except HTTPError as error:
            if 300 <= error.code < 400:
                raise ValueError("Bridge redirect refused; no credential forwarded.") from None
            raise ValueError(f"Cabinet command refused (HTTP {error.code}); no success confirmed.") from None
        if len(body) > 4 * 1024 * 1024:
            raise ValueError("Response too large; request a narrower record or period.")
        return json.loads(body)

    def status(self):
        status = self._request("/status")
        cabinet = status.get("native_cabinet") if isinstance(status, dict) else None
        if not isinstance(cabinet, dict) or status.get("product") != "Actelyo ERP" or cabinet.get("version") != 1:
            raise ValueError("This ERP does not expose the cabinet service; update it first.")
        # Approval cards can contain private details; do not include them in discovery.
        return {"product": status["product"], "cabinet": status["native_cabinet"]}

    def dossiers(self):
        self.status()
        return self._request("/dossiers")

    def call(self, action: str, fields: dict, dossier_id: str | None = None):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", action) or not isinstance(fields, dict):
            raise ValueError("Action and JSON object required.")
        self.status()
        payload = {"action": action, "input": fields}
        if dossier_id:
            payload["dossierId"] = dossier_id
        result = self._request("/cabinet", payload)
        if not isinstance(result, dict):
            raise ValueError("Invalid native execution receipt.")
        if result.get("cancelled"):
            return {"cancelled": True, "confirmed": False}
        if result.get("isError") or "content" not in result:
            raise ValueError("No native execution receipt returned.")
        if not isinstance(result["content"], list) or any(not isinstance(block, dict) for block in result["content"]):
            raise ValueError("Invalid native receipt content.")
        blocks = [block.get("text") for block in result["content"] if block.get("type") == "text"]
        if len(blocks) != 1 or not isinstance(blocks[0], str):
            raise ValueError("Unexpected native cabinet receipt.")
        return {"confirmed": True, "result": json.loads(blocks[0])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", type=Path, required=True, help="ERP profile ecosystem-bridge.json; never print its contents")
    parser.add_argument("--receipt", type=Path, help="New local receipt file; existing files are preserved")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("dossiers")
    call = sub.add_parser("call")
    call.add_argument("action")
    call.add_argument("--input-file", type=Path, required=True)
    call.add_argument("--dossier")
    args = parser.parse_args(argv)
    try:
        client = CabinetClient(args.bridge)
        if args.command == "status":
            result = client.status()
        elif args.command == "dossiers":
            result = client.dossiers()
        else:
            if args.input_file.stat().st_size > 100000:
                raise ValueError("Input JSON too large.")
            result = client.call(args.action, json.loads(args.input_file.read_text(encoding="utf-8-sig")), args.dossier)
        # JSON escapes preserve all Unicode through Windows legacy pipe encodings.
        text = json.dumps(result, ensure_ascii=True, indent=2)
        if args.receipt:
            with args.receipt.open("x", encoding="utf-8") as output:
                output.write(text)
        print(text)
        return 3 if result.get("cancelled") else 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"confirmed": False, "error": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
