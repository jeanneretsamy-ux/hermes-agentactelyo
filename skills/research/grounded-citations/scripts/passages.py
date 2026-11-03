"""Immutable passage selection and mechanically assembled citation references.

Offsets are Unicode character offsets in the supplied extracted source text,
not PDF coordinates or binary file offsets. Missing page numbers stay unknown.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
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

        if source_name(source).lower().endswith((".csv", ".tsv")):
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


def verify_bindings(claims, sources):
    catalog = build_catalog(sources)
    errors = []
    for claim in claims:
        for evidence in claim.get("evidence", []):
            expected = catalog.get(evidence.get("passage_id"))
            if expected is None or evidence != expected:
                errors.append(f"{claim['id']}: citation does not match its source snapshot and location.")
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
        text = claim["text"].replace("[", "\\[").replace("]", "\\]")
        lines.append(text + " " + "".join(labels) + "\n")
    lines += ["## Sources", ""]
    for number, evidence in references.values():
        page = f"page {evidence['page']}" if evidence["page"] is not None else "page non renseignée"
        name = evidence["name"].replace("[", "\\[").replace("]", "\\]")
        lines += [f"[{number}] {name} — {page}, caractères {evidence['start']}–{evidence['end']} du texte extrait.",
                  evidence["url"], f"Passage : `{evidence['passage_id']}` · SHA-256 : `{evidence['source_sha256']}`", ""]
        if "table" in evidence:
            lines += [f"Ligne {evidence['table']['row']} du tableau extrait · Colonnes : " + " | ".join(evidence["table"]["headers"]), ""]
        lines += ["> " + line for line in evidence["quote"].splitlines()] + [""]
    return "\n".join(lines)
