"""Immutable passage selection and mechanically assembled citation references.

Offsets are Unicode character offsets in the supplied extracted source text,
not PDF coordinates or binary file offsets. Missing page numbers stay unknown.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import unicodedata
from urllib.parse import unquote, urlparse


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_name(source):
    return source.get("name") or unquote(PurePosixPath(urlparse(source["url"]).path).name) or source["url"]


def _trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end-1].isspace():
        end -= 1
    return start, end


def _csv_rows(text, delimiter):
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1]+len(line))
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    previous = 0
    for cells in reader:
        end_line = reader.line_num
        start, end = _trim(text, offsets[previous], offsets[end_line])
        yield start, end, cells
        previous = end_line


def build_catalog(sources):
    catalog = {}
    for source_id, source in sources.items():
        text = source["text"]
        snapshot = digest(text)
        page = source.get("page")
        if page is not None and (type(page) is not int or page < 1):
            raise ValueError("Page must be a positive integer or unknown.")
        document_id = source.get("document_id") or digest(source["url"])

        def add(start, end, table=None):
            start, end = _trim(text, start, end)
            if start == end:
                return
            identity = [document_id, source["url"], page, snapshot, start, end]
            pid = "p_" + digest(json.dumps(identity, ensure_ascii=False))[:24]
            item = {"passage_id": pid, "source_id": str(source_id), "document_id": document_id,
                    "name": source_name(source), "url": source["url"], "page": page,
                    "start": start, "end": end, "offset_scope": "supplied_source_text",
                    "source_sha256": snapshot, "quote": text[start:end]}
            if table:
                item["table"] = table
            if pid in catalog and catalog[pid] != item:
                raise ValueError("Duplicate source snapshot or passage identity collision.")
            catalog[pid] = item

        extracted_markdown = bool(re.match(r"\s*\|[^\n]+\n\|\s*:?-{3}", text))
        if source_name(source).lower().endswith((".csv", ".tsv")) and not extracted_markdown:
            delimiter = "\t" if source_name(source).lower().endswith(".tsv") else ";"
            if delimiter == ";" and ";" not in text.splitlines()[0]:
                delimiter = ","
            rows = list(_csv_rows(text, delimiter))
            if not rows:
                continue
            hs, he, headers = rows[0]
            for row_number, (start, end, cells) in enumerate(rows[1:], 2):
                if len(cells) != len(headers):
                    raise ValueError("Ragged table: column associations cannot be verified.")
                add(start, end, {"row": row_number, "headers": headers,
                    "cells": [{"column": i+1, "header": h, "value": v} for i, (h, v) in enumerate(zip(headers, cells))],
                    "header_quote": text[hs:he], "header_start": hs, "header_end": he})
            continue

        # Extract Markdown/TSV rows as units; retain headers even when a selected
        # row is far from the table's first line in a long source.
        lines = text.splitlines(keepends=True)
        offsets, cursor = [], 0
        for line in lines:
            offsets.append(cursor)
            cursor += len(line)
        occupied = []
        i = 0
        while i < len(lines)-1:
            line = lines[i].rstrip("\r\n")
            delimiter = "\t" if "\t" in line else "|" if line.strip().startswith("|") else None
            if not delimiter:
                i += 1
                continue
            def cells_for(value):
                value = value.strip().strip("|") if delimiter == "|" else value.rstrip("\r\n")
                return [c.strip() for c in next(csv.reader([value], delimiter=delimiter,
                    escapechar="\\" if delimiter == "|" else None, quoting=csv.QUOTE_NONE))]
            headers = cells_for(line)
            if len(headers) < 2 or delimiter not in lines[i+1]:
                i += 1
                continue
            start_table, j, row_number = i, i+1, 1
            while j < len(lines) and delimiter in lines[j]:
                cells = cells_for(lines[j])
                if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    j += 1
                    continue
                if len(cells) != len(headers):
                    raise ValueError("Ragged extracted table: verify its structure before citation.")
                row_number += 1
                hs, he = _trim(text, offsets[i], offsets[i]+len(lines[i]))
                add(offsets[j], offsets[j]+len(lines[j]), {"row": row_number, "headers": headers,
                    "cells": [{"column": n+1, "header": h, "value": v} for n, (h, v) in enumerate(zip(headers, cells))],
                    "header_quote": text[hs:he], "header_start": hs, "header_end": he})
                j += 1
            occupied.append((offsets[start_table], offsets[j] if j < len(lines) else len(text)))
            i = j

        start = 0
        for boundary in list(re.finditer(r"(?<=[.!?])\s+|\n+", text)) + [None]:
            end = boundary.start() if boundary else len(text)
            if not any(start < right and end > left for left, right in occupied):
                while end-start > 1200:
                    cut = text.rfind(" ", start+600, start+1200)
                    cut = cut if cut > start else start+1200
                    add(start, cut)
                    start = cut
                add(start, end)
            start = boundary.end() if boundary else len(text)
    if not catalog:
        raise ValueError("No citable passages in the source bundle.")
    return catalog


def assemble_claims(selected, catalog):
    if not isinstance(selected, list) or not selected:
        raise ValueError("No selected claims.")
    result, seen = [], set()
    for claim in selected:
        if not isinstance(claim, dict) or set(claim)-{"id", "text", "passage_ids"}:
            raise ValueError("Claims must select passage_ids; model-authored citation fields are forbidden.")
        cid, text, ids = claim.get("id"), claim.get("text"), claim.get("passage_ids")
        if not isinstance(cid, str) or not cid or cid in seen or not isinstance(text, str) or not text.strip():
            raise ValueError("Invalid or duplicate claim id/text.")
        if not isinstance(ids, list) or not ids or any(not isinstance(pid, str) or pid not in catalog for pid in ids):
            raise ValueError(f"{cid}: unknown or missing passage identifier.")
        if len(ids) != len(set(ids)):
            raise ValueError(f"{cid}: duplicate passage selection.")
        seen.add(cid)
        # All citation fields come from the immutable catalog, never the model.
        result.append({"id": cid, "text": text, "evidence": [dict(catalog[pid]) for pid in ids]})
    return result


def select_context(catalog, question, limit=None):
    """Bound small local-model context using only the question, never gold labels."""
    if limit is None or limit >= len(catalog):
        return catalog
    if type(limit) is not int or limit < 1:
        raise ValueError("Passage limit must be a positive integer.")
    stop = set("le la les de du des un une et est en au aux pour par sur dans quel quelle quels quelles ce cette ces a il elle que qui comment avec document documents dossier the is of what which".split())
    def words(text):
        plain = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
        return {word for word in re.findall(r'\w+', plain) if len(word)>1 and word not in stop}
    terms = words(question)
    def key(item):
        _, row = item
        content = row['quote'] + ' ' + json.dumps(row.get('table', {}), ensure_ascii=False)
        relevance = len(terms & words(content)) + 2*len(terms & words(row['name']))
        return -relevance, row['url'], row['start']
    return dict(sorted(catalog.items(), key=key)[:limit])


def verify_bindings(claims, sources):
    catalog = build_catalog(sources)
    errors = []
    for claim in claims:
        for evidence in claim.get("evidence", []):
            expected = catalog.get(evidence.get("passage_id"))
            if expected is None or evidence != expected:
                errors.append(f"{claim['id']}: citation does not match its source snapshot and location.")
    return errors


def verify_table_amounts(question, claims, catalog):
    """Reject detectable row/financial-column conflicts; not a truth oracle."""
    def normal(text):
        return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    def number(text):
        text = re.sub(r'[\s\u202f€]', '', text).replace(',', '.')
        try:
            value = Decimal(text)
            return value if value.is_finite() else None
        except InvalidOperation:
            return None
    q = normal(question)
    tokens = ' '.join(re.findall(r'\w+', q))
    months = {name: str(i).zfill(2) for i, name in enumerate(
        ('janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre'), 1)}
    dates = {f"{int(d):02}/{int(m):02}/{y}" for d, m, y in re.findall(r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', q)}
    for day, month, year in re.findall(r'\b(\d{1,2})(?:er)?\s+([a-z]+)\s+(\d{4})\b', q):
        if month in months:
            dates.add(f"{int(day):02}/{months[month]}/{year}")
    if re.search(r'\b(?:avant|apres|depuis|entre|jusqu|anterieur|posterieur)\b', q):
        dates = set()  # A range/boundary question is not an exact-date lookup.
    rows = {(row['source_id'], row['start'], row['end']): row['table'] for row in catalog.values() if 'table' in row}
    def row_score(table):
        score = 0
        for cell in table['cells']:
            value_date = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', cell['value'].strip())
            if value_date:
                day, month, year = value_date.groups()
                if f"{int(day):02}/{int(month):02}/{year}" in dates:
                    score += 2
            if normal(cell['header']) not in ('dossier', 'facture', 'reference', 'client', 'id'):
                continue
            value = ' '.join(re.findall(r'\w+', normal(cell['value'])))
            if value and re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)', tokens):
                score += 1
        return score
    scores = {key: row_score(table) for key, table in rows.items()}
    best = max(scores.values(), default=0)
    errors = []
    for claim in claims:
        tables = [((e['source_id'], e['start'], e['end']), e['table']) for e in claim['evidence'] if 'table' in e]
        if not tables:
            continue
        text = normal(claim['text'])
        fields = {field for field in ('ttc', 'ht', 'tva') if re.search(r'\b'+field+r'\b', text)}
        if not fields:
            fields = {normal(h) for _, table in tables for h in table['headers']
                      if normal(h) in ('montant', 'total', 'prix', 'loyer') and re.search(r'\b'+normal(h)+r'\b', text)}
        if not fields:
            continue
        if len(fields)>1:
            errors.append(f"{claim['id']}: split financial fields into separate claims.")
            continue
        field = next(iter(fields))
        expected = set()
        for key, table in tables:
            if best and scores.get(key, 0)<best:
                continue
            for cell in table['cells']:
                if re.search(r'\b'+re.escape(field)+r'\b', normal(cell['header'])):
                    value = number(cell['value'])
                    if value is not None:
                        expected.add(value)
        stated = {number(m.group()) for m in re.finditer(r'(?<![\w/\-])-?\d(?:[\d\s.,\u202f]*\d)?(?![\w/\-])', text)}
        stated.discard(None)
        if not expected or not expected.intersection(stated):
            errors.append(f"{claim['id']}: amount conflicts with the referenced {field} column or dossier/invoice row.")
    return errors


def render_report(result):
    if result["status"] not in ("approved", "experimental_review_passed"):
        return "# Recherche incomplète\n\nLes affirmations n'ont pas passé le contrôle des preuves.\n"
    lines = ["# Recherche documentée", ""]
    if result.get("requires_human_review"):
        lines += ["**Expérimental — revue humaine requise.**", ""]
    references = {}
    for claim in result["claims"]:
        labels = []
        for evidence in claim["evidence"]:
            pid = evidence["passage_id"]
            if pid not in references:
                references[pid] = (len(references)+1, evidence)
            labels.append(f"[{references[pid][0]}]")
        # Prevent model-authored reference numbers or Markdown links from being
        # confused with mechanically attached citations.
        text = claim["text"].replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;").replace("[", "\\[").replace("]", "\\]")
        lines.append("- " + text + " " + "".join(labels) + "\n")
    lines += ["## Sources", ""]
    for number, evidence in references.values():
        page = f"page {evidence['page']}" if evidence["page"] is not None else "page non renseignée"
        name = evidence["name"].replace("[", "\\[").replace("]", "\\]")
        lines += [f"[{number}] {name} — {page}, caractères {evidence['start']}–{evidence['end']} du texte extrait.",
                  evidence["url"], f"Passage : `{evidence['passage_id']}` · SHA-256 : `{evidence['source_sha256']}`", ""]
        if "table" in evidence:
            lines += [f"Ligne {evidence['table']['row']} du tableau extrait · Colonnes : " + " | ".join(evidence["table"]["headers"]), ""]
        ticks = max((len(run) for run in re.findall(r'`+', evidence["quote"])), default=0)
        fence = '`' * max(3, ticks+1)
        lines += [fence+'text', evidence["quote"], fence, ""]
    return "\n".join(lines)
