"""Profile-owned, versioned research panels. No generated code is executed.

The first panel contract is a chronology. Source binding proves the supplied
extracted text, not authenticity of the original document or legal entailment.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from urllib.parse import urlparse

from hermes_constants import get_bundled_skills_dir, get_hermes_home, mkdir_under_hermes_home


def _passages():
    path = get_bundled_skills_dir(Path(__file__).resolve().parents[1] / 'skills') / "research/grounded-citations/scripts/passages.py"
    if not path.is_file():
        raise ValueError("Le module de citations n'est pas installé dans ce runtime.")
    spec = importlib.util.spec_from_file_location("_atelier_passages", path)
    if spec is None or spec.loader is None:
        raise ValueError("Le module de citations n'est pas installé.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(value, label, maximum=500):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"Champ invalide : {label}.")
    return value.strip()


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError("Champs manquants ou inconnus dans l'extension.")


def _date_in_text(day, text):
    plain = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    months = ('janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre')
    patterns = (re.escape(day.isoformat()), rf"{day.day:02}/{day.month:02}/{day.year}",
                rf"{day.day}/{day.month}/{day.year}", rf"{day.day}(?:er)?\s+{months[day.month-1]}\s+{day.year}")
    return any(re.search(r"(?<!\w)" + p + r"(?!\w)", plain) for p in patterns)


def source_catalog(raw_sources):
    if not isinstance(raw_sources, list) or not 1 <= len(raw_sources) <= 30:
        raise ValueError("Fournissez entre 1 et 30 sources extraites.")
    sources = {}
    for row in raw_sources:
        _fields(row, ('id', 'name', 'url', 'text'), ('page', 'document_id'))
        sid = _text(row['id'], 'source.id', 80)
        if sid in sources:
            raise ValueError("Identifiant de source dupliqué.")
        _text(row['name'], 'source.name', 240)
        _text(row['text'], 'source.text', 100_000)
        url = _text(row['url'], 'source.url', 2000)
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https', 'file') or parsed.username or parsed.password:
            raise ValueError("Adresse de source invalide.")
        if row.get('document_id') is not None:
            _text(row['document_id'], 'document_id', 240)
        sources[sid] = {**row, 'id': sid}
    return _passages().build_catalog(sources)


def validate_bundle(bundle):
    _fields(bundle, ('schema_version', 'id', 'name', 'kind', 'sources', 'events'))
    if type(bundle['schema_version']) is not int or bundle['schema_version'] != 1 or bundle['kind'] != 'chronology':
        raise ValueError("Seule la chronologie au format 1 est prise en charge.")
    panel_id = _text(bundle['id'], 'id', 64)
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', panel_id):
        raise ValueError("Identifiant d'extension invalide.")
    name = _text(bundle['name'], 'name', 120)
    encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if len(encoded.encode('utf-8')) > 2_000_000:
        raise ValueError("Extension trop volumineuse (maximum 2 Mo).")
    passages = _passages()
    catalog = source_catalog(bundle['sources'])
    raw_events = bundle['events']
    if not isinstance(raw_events, list) or not 1 <= len(raw_events) <= 200:
        raise ValueError("Fournissez entre 1 et 200 événements.")
    events, seen = [], set()
    for event in raw_events:
        _fields(event, ('id', 'date', 'title', 'passage_ids'))
        eid = _text(event['id'], 'event.id', 80)
        if eid in seen:
            raise ValueError("Identifiant d'événement dupliqué.")
        seen.add(eid)
        day = date.fromisoformat(_text(event['date'], 'date', 10))
        title = _text(event['title'], 'title', 500)
        claims = passages.assemble_claims([{'id': eid, 'text': title, 'passage_ids': event['passage_ids']}], catalog)
        evidence = claims[0]['evidence']
        if not any(_date_in_text(day, e['quote']) for e in evidence):
            raise ValueError(f"La date de {eid} n'existe pas dans ses passages cités.")
        events.append({'id': eid, 'date': day.isoformat(), 'title': title, 'evidence': evidence})
    events.sort(key=lambda e: (e['date'], e['id']))
    return {'id': panel_id, 'name': name, 'kind': 'chronology', 'revision': hashlib.sha256(encoded.encode('utf-8')).hexdigest(),
            'events': events, 'source_binding': 'verified', 'semantic_review': 'human_required'}


@contextmanager
def _db():
    home = get_hermes_home()
    mkdir_under_hermes_home(home)
    conn = sqlite3.connect(home / 'atelier.sqlite3', timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript('''
          CREATE TABLE IF NOT EXISTS revisions (
            revision TEXT PRIMARY KEY, panel_id TEXT NOT NULL, name TEXT NOT NULL,
            bundle TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
          CREATE TABLE IF NOT EXISTS active (panel_id TEXT PRIMARY KEY, revision TEXT NOT NULL);
        ''')
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def snapshot():
    with _db() as conn:
        revisions = [dict(row) for row in conn.execute('''SELECT r.panel_id AS id, r.name, r.revision, r.created_at,
            CASE WHEN a.revision=r.revision THEN 1 ELSE 0 END AS active FROM revisions r
            LEFT JOIN active a ON a.panel_id=r.panel_id ORDER BY r.created_at DESC, r.revision''')]
        return {'revisions': [{**row, 'active': bool(row['active'])} for row in revisions]}


def save(bundle):
    panel = validate_bundle(bundle)
    with _db() as conn:
        conn.execute('INSERT OR IGNORE INTO revisions(revision,panel_id,name,bundle) VALUES(?,?,?,?)',
                     (panel['revision'], panel['id'], panel['name'], json.dumps(bundle, ensure_ascii=False)))
    return panel


def preview(revision):
    if not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{64}', revision):
        raise ValueError("Révision invalide.")
    with _db() as conn:
        row = conn.execute('SELECT bundle FROM revisions WHERE revision=?', (revision,)).fetchone()
    if row is None:
        raise ValueError("Cette version n'existe pas dans ce profil.")
    panel = validate_bundle(json.loads(row['bundle']))
    if panel['revision'] != revision:
        raise ValueError("Le contenu de cette version a changé.")
    return panel


def activate(revision):
    panel = preview(revision)
    with _db() as conn:
        conn.execute('INSERT INTO active(panel_id,revision) VALUES(?,?) ON CONFLICT(panel_id) DO UPDATE SET revision=excluded.revision',
                     (panel['id'], revision))
    return snapshot()


def deactivate(panel_id):
    with _db() as conn:
        conn.execute('DELETE FROM active WHERE panel_id=?', (panel_id,))
    return snapshot()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Atelier Actelyo : extensions de chronologie sourcées.')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list')
    sub.add_parser('catalog').add_argument('sources', type=Path)
    sub.add_parser('save').add_argument('bundle', type=Path)
    sub.add_parser('preview').add_argument('revision')
    args = parser.parse_args(argv)
    if args.action == 'list':
        result = snapshot()
    elif args.action == 'preview':
        result = preview(args.revision)
    else:
        path = args.sources if args.action == 'catalog' else args.bundle
        if path.stat().st_size > 2_000_000:
            raise ValueError('Fichier trop volumineux.')
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if args.action == 'catalog':
            result = list(source_catalog(data).values())
        else:
            result = save(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
