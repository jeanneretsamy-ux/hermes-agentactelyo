"""Loopback HTTP API and MCP stdio adapters for a single configured principal."""
from __future__ import annotations

import hmac
import json
import os
import secrets
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

from .core import HarnessError, require, secret


def dispatch(harness, name, arguments):
    require(isinstance(arguments, dict), "Arguments objet requis")
    if name == "law_status":
        require(not arguments, "law_status n'accepte pas d'arguments")
        return harness.doctor()
    if name == "law_review_contract":
        require(set(arguments) == {"request"}, "Argument request requis")
        return harness.review(arguments["request"])
    if name == "law_search":
        require({"source", "query", "as_of"} <= set(arguments)
                and set(arguments) <= {"source", "query", "as_of", "limit"}, "Arguments recherche invalides")
        return harness.search(**arguments)
    if name == "law_fetch":
        require(set(arguments) == {"source", "source_id", "as_of"}, "Arguments consultation invalides")
        return harness.fetch(**arguments).as_dict()
    raise HarnessError("Outil inconnu")


REQUEST_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["task", "matter_id", "jurisdiction", "as_of", "documents"],
    "properties": {"task": {"const": "contract_review"}, "matter_id": {"type": "string"},
                   "jurisdiction": {"const": "FR"}, "as_of": {"type": "string", "format": "date"},
                   "instruction": {"type": "string", "maxLength": 4000},
                   "documents": {"type": "array", "minItems": 1, "maxItems": 10,
                                 "items": {"type": "object", "required": ["id", "text"],
                                           "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                                           "additionalProperties": False}}}}


def tools_list():
    return [
        {"name": "law_status", "description": "État configuré du harness, sans vérification des fournisseurs.",
         "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        {"name": "law_review_contract", "description": "Revue contractuelle FR sourcée. Toujours un brouillon à valider.",
         "inputSchema": {"type": "object", "properties": {"request": REQUEST_SCHEMA},
                         "required": ["request"], "additionalProperties": False}},
        {"name": "law_search", "description": "Recherche juridique limitée, dans les sources autorisées du principal.",
         "inputSchema": {"type": "object", "required": ["source", "query", "as_of"],
                         "additionalProperties": False, "properties": {
                             "source": {"enum": ["legifrance", "legal_data_hunter"]},
                             "query": {"type": "string", "maxLength": 500},
                             "as_of": {"type": "string", "format": "date"},
                             "limit": {"type": "integer", "minimum": 1, "maximum": 10}}}},
        {"name": "law_fetch", "description": "Consulte une preuve complète et indique l'état de vérification de sa date.",
         "inputSchema": {"type": "object", "required": ["source", "source_id", "as_of"],
                         "additionalProperties": False, "properties": {
                             "source": {"enum": ["legifrance", "legal_data_hunter"]},
                             "source_id": {"type": "string"}, "as_of": {"type": "string", "format": "date"}}}}
    ]


def make_http_server(harness, port: int, token: str):
    require(len(token) >= 32, "ACTELYO_HARNESS_TOKEN doit contenir au moins 32 caractères")
    lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Do not log request bodies or credentials.

        def send_json(self, code, value):
            raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self):
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied.encode(), f"Bearer {token}".encode()):
                self.send_json(401, {"error": "Authentification requise"})
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/health":
                self.send_json(200, harness.doctor())
            else:
                self.send_json(404, {"error": "Route inconnue"})

        def do_POST(self):
            if not self.authorized():
                return
            names = {"/v1/reviews": "law_review_contract", "/v1/search": "law_search", "/v1/fetch": "law_fetch"}
            if self.path not in names:
                self.send_json(404, {"error": "Route inconnue"})
                return
            if not lock.acquire(blocking=False):
                self.send_json(429, {"error": "Une opération est déjà en cours pour ce principal"})
                return
            try:
                self.connection.settimeout(15)
                length = int(self.headers.get("Content-Length", "0"))
                require(0 < length <= 1_000_000, "Corps de requête vide ou trop volumineux")
                require(self.headers.get("Content-Type", "").split(";")[0].strip() == "application/json", "Content-Type application/json requis")
                body = json.loads(self.rfile.read(length))
                args = {"request": body} if self.path == "/v1/reviews" else body
                result = dispatch(harness, names[self.path], args)
                self.send_json(200, result)
            except (HarnessError, ValueError, TypeError, TimeoutError) as exc:
                message = str(exc) if isinstance(exc, HarnessError) else "Requête JSON invalide ou délai dépassé"
                self.send_json(400, {"error": message})
            except Exception:
                self.send_json(500, {"error": "Erreur interne ; aucune conclusion juridique validée"})
            finally:
                lock.release()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def connection_manifest(server, token, destination):
    """Explicit private connection file for the ERP main process; never a renderer key."""
    target = Path(destination).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".law-connection-", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"schema_version": 1, "endpoint": f"http://127.0.0.1:{server.server_port}",
                       "token": token}, handle)
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def serve_http(harness, port, connection_file=None):
    token = os.environ.get("ACTELYO_HARNESS_TOKEN")
    if not token:
        token = secrets.token_urlsafe(32) if connection_file else secret("ACTELYO_HARNESS_TOKEN")
    server = make_http_server(harness, port, token)
    if connection_file:
        connection_manifest(server, token, connection_file)
    print(f"Actelyo Law Harness écoute sur http://127.0.0.1:{server.server_port}", file=sys.stderr)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def mcp_reply(harness, message):
    require(isinstance(message, dict), "Message JSON-RPC objet requis")
    if "id" not in message:
        return None  # Notifications, including initialized/cancelled.
    identifier = message["id"]
    try:
        require(message.get("jsonrpc") == "2.0", "JSON-RPC 2.0 requis")
        method, params = message.get("method"), message.get("params", {})
        require(isinstance(params, dict), "Paramètres JSON-RPC invalides")
        if method == "initialize":
            # No experimental capabilities: basic stdio tools only.
            supported = {"2024-11-05", "2025-03-26", "2025-06-18"}
            requested = params.get("protocolVersion")
            result = {"protocolVersion": requested if requested in supported else "2025-06-18",
                      "capabilities": {"tools": {}},
                      "serverInfo": {"name": "actelyo-law-harness", "version": "0.1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": tools_list()}
        elif method == "tools/call":
            try:
                output = dispatch(harness, params.get("name"), params.get("arguments", {}))
                result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}], "isError": False}
            except HarnessError as exc:
                result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
        else:
            return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32601, "message": "Méthode inconnue"}}
        return {"jsonrpc": "2.0", "id": identifier, "result": result}
    except HarnessError as exc:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32602, "message": str(exc)}}


def serve_mcp(harness):
    # MCP stdio: one JSON-RPC message per line. stdout is reserved for the protocol.
    for line in sys.stdin:
        try:
            require(len(line) <= 1_000_000, "Message MCP trop volumineux")
            reply = mcp_reply(harness, json.loads(line))
        except (HarnessError, ValueError):
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Message JSON invalide"}}
        except Exception:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Erreur interne"}}
        if reply is not None:
            print(json.dumps(reply, ensure_ascii=False), flush=True)
