#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

API_BASE = os.environ.get("ACTELYO_RAG_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("ACTELYO_RAG_API_KEY", "")
DEFAULT_WORKSPACE = os.environ.get("ACTELYO_RAG_WORKSPACE", "mon-espace-de-travail")


def api_base():
    if API_BASE:
        endpoint = urllib.parse.urlparse(API_BASE)
        loopback = endpoint.hostname in {'localhost', '127.0.0.1', '::1'}
        if (endpoint.scheme != 'https' and not (endpoint.scheme == 'http' and loopback)
                or not endpoint.hostname or endpoint.username or endpoint.password
                or endpoint.query or endpoint.fragment):
            raise RuntimeError('Invalid RAG API address. Use HTTPS or loopback HTTP without embedded credentials.')
        return API_BASE.removesuffix('/v1')
    # The desktop app allocates a fresh loopback port on every launch. Resolve
    # it per request so an existing MCP process also follows a RAG restart.
    appdata = os.environ.get("APPDATA")
    if appdata:
        receipt = Path(appdata) / "Actelyo RAG" / "desktop-service.json"
        if receipt.exists():
            try:
                if receipt.stat().st_size > 4096:
                    raise ValueError('oversized receipt')
                record = json.loads(receipt.read_text(encoding='utf-8'))
                endpoint = urllib.parse.urlparse(record['apiBase'])
                if (record.get('schemaVersion') != 1 or record.get('product') != 'Actelyo RAG'
                        or not isinstance(record.get('pid'), int) or record['pid'] <= 0
                        or endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1'
                        or endpoint.path != '/api/v1' or not endpoint.port
                        or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
                    raise ValueError('invalid receipt')
                if record.get('state') == 'stopped':
                    raise RuntimeError('Actelyo RAG is stopped. Start the Desktop app before searching.')
                return record['apiBase'].removesuffix('/v1')
            except (OSError, ValueError, KeyError, TypeError):
                raise RuntimeError('Invalid Actelyo RAG Desktop service announcement.') from None
        log = Path(appdata) / "Actelyo RAG" / "desktop.log"
        try:
            with log.open("rb") as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 1024 * 1024))
                text = stream.read().decode("utf-8", errors="replace")
            ports = re.findall(r"Primary server in HTTP mode listening on port (\d+)", text)
            if ports and 1024 <= int(ports[-1]) <= 65535:
                return f"http://127.0.0.1:{ports[-1]}/api"
        except OSError:
            pass
    raise RuntimeError('Actelyo RAG is not detected. Start the Desktop app or configure its API address.')


def _headers():
    if not API_KEY:
        raise RuntimeError("ACTELYO_RAG_API_KEY is not configured in the local .env")
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _request(method, path, payload=None):
    url = f"{api_base()}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=_headers())
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as res:
            raw = res.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Actelyo RAG HTTP {exc.code}: request not completed; no redirect or provider fallback.") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Actelyo RAG is not reachable at {url}: {exc.reason}")


def _tool_result(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, indent=2)}]}


def list_workspaces(_args):
    return _tool_result(_request("GET", "/v1/workspaces"))


def _workspace(args):
    slug = (args or {}).get('workspace') or DEFAULT_WORKSPACE
    if not isinstance(slug, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,160}', slug):
        raise RuntimeError('Invalid Actelyo RAG workspace identifier.')
    return slug


def query(args):
    prompt = (args or {}).get("prompt") or (args or {}).get("query")
    if not prompt:
        raise RuntimeError("Missing required argument: prompt")
    slug = _workspace(args)
    mode = (args or {}).get("mode") or "query"
    payload = {"message": prompt, "mode": mode}
    if (args or {}).get("sessionId"):
        payload["sessionId"] = args["sessionId"]
    return _tool_result(_request("POST", f"/v1/workspace/{urllib.parse.quote(slug)}/chat", payload))


def vector_search(args):
    query_text = (args or {}).get("query")
    if not query_text:
        raise RuntimeError("Missing required argument: query")
    slug = _workspace(args)
    payload = {"query": query_text}
    if (args or {}).get("topN") is not None:
        payload["topN"] = args["topN"]
    return _tool_result(_request("POST", f"/v1/workspace/{urllib.parse.quote(slug)}/vector-search", payload))


TOOLS = {
    "actelyo_rag_list_workspaces": {
        "description": "List Actelyo RAG workspaces available through the local Actelyo RAG backend.",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": list_workspaces,
    },
    "actelyo_rag_query": {
        "description": "Ask Actelyo RAG a question against an indexed workspace. Use mode='query' for source-grounded retrieval and mode='chat' for normal RAG chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "workspace": {"type": "string", "default": DEFAULT_WORKSPACE},
                "mode": {"type": "string", "enum": ["query", "chat", "automatic"], "default": "query"},
                "sessionId": {"type": "string"},
            },
            "required": ["prompt"],
        },
        "handler": query,
    },
    "actelyo_rag_vector_search": {
        "description": "Run a vector search in an Actelyo RAG workspace and return retrieved source chunks without asking the LLM to answer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "workspace": {"type": "string", "default": DEFAULT_WORKSPACE},
                "topN": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
        "handler": vector_search,
    },
}


def send(msg):
    sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def handle(req):
    method = req.get("method")
    if method == "initialize":
        return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "actelyo-rag", "version": "1.0.0"}}
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"tools": [{"name": name, "description": meta["description"], "inputSchema": meta["inputSchema"]} for name, meta in TOOLS.items()]}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        if name not in TOOLS:
            raise RuntimeError(f"Unknown tool: {name}")
        return TOOLS[name]["handler"](params.get("arguments") or {})
    raise RuntimeError(f"Unsupported method: {method}")


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            result = handle(req)
            if req.get("id") is not None and result is not None:
                send({"jsonrpc": "2.0", "id": req.get("id"), "result": result})
        except Exception as exc:
            if 'req' in locals() and req.get("id") is not None:
                send({"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32000, "message": str(exc)}})


if __name__ == "__main__":
    main()

