"""Transactional import of user-owned reference acts; no bundled corpus."""
import hashlib
import json
import secrets


def import_library(conn, project_id, params):
    from hermes_cli.legal_practice import _legal_text

    workspace = conn.execute('SELECT domain FROM legal_workspaces WHERE project_id=?', (project_id,)).fetchone()
    if not workspace or params.get('domain') != workspace['domain']:
        raise ValueError('Le domaine de la bibliothèque doit correspondre à celui de cet espace.')
    entries = params.get('entries')
    if not isinstance(entries, list) or not 1 <= len(entries) <= 500:
        raise ValueError('Importer entre 1 et 500 actes à la fois.')
    if len(json.dumps(entries, ensure_ascii=False)) > 8_000_000:
        raise ValueError('Bibliothèque trop volumineuse ; scinder le fichier.')
    for entry in entries:
        title = _legal_text(entry.get('title'), required=True, limit=500)
        kind = _legal_text(entry.get('act_type'), required=True, limit=100)
        body = _legal_text(entry.get('body'), required=True, limit=200_000)
        digest = hashlib.sha256(json.dumps([title, kind, body], ensure_ascii=False).encode()).hexdigest()
        if conn.execute('SELECT 1 FROM legal_library_imports WHERE project_id=? AND digest=?', (project_id, digest)).fetchone():
            continue
        act_id = secrets.token_hex(16)
        conn.execute('INSERT INTO legal_acts (id,project_id,title,act_type,body) VALUES (?,?,?,?,?)',
                     (act_id, project_id, title, kind, body))
        conn.execute('INSERT INTO legal_library_imports (project_id,digest,act_id) VALUES (?,?,?)',
                     (project_id, digest, act_id))
