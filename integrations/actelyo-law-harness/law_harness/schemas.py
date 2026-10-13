"""Schemas shared by prompts and constrained model generation."""
import copy
from .core import require
STRING = {"type": "string"}
STRINGS = {"type": "array", "items": STRING}

PLAN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["issues", "queries"],
    "properties": {
        "issues": {"type": "array", "maxItems": 20, "items": {"type": "string", "minLength": 1, "maxLength": 1000}},
        "queries": {"type": "array", "minItems": 1, "maxItems": 4,
                    "items": {"type": "string", "minLength": 1, "maxLength": 500}}}}

REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["summary", "risks", "open_questions"],
    "properties": {"summary": STRING, "open_questions": STRINGS,
        "risks": {"type": "array", "maxItems": 20, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["clause", "issue", "severity", "analysis", "proposal", "citations", "limitations"],
            "properties": {
                "clause": {"type": "object", "additionalProperties": False,
                           "required": ["document_id", "quote"],
                           "properties": {"document_id": STRING, "quote": STRING}},
                "issue": STRING, "severity": {"enum": ["low", "medium", "high"]},
                "analysis": STRING, "proposal": STRING, "limitations": STRINGS,
                "citations": {"type": "array", "minItems": 1, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["evidence_id", "quote"],
                    "properties": {"evidence_id": STRING, "quote": STRING}}}}}}}}


def quote_choices(text, minimum):
    """Literal windows only; full source text remains available in the model context."""
    passages = []
    for line in text.splitlines():
        line = line.strip()
        start = 0
        while start < len(line):
            end = min(start + 800, len(line))
            if end < len(line):
                boundary = line.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            passage = line[start:end].strip()
            if len(passage) >= minimum:
                passages.append(passage)
            start = end
            while start < len(line) and line[start].isspace():
                start += 1
    passages = list(dict.fromkeys(passages))
    require(len(passages) <= 256, "Trop de passages citables ; découpage explicite requis")
    return passages


def reference_schema(references, identifier, minimum):
    branches = []
    for key, text in references:
        choices = quote_choices(text, minimum)
        if choices:
            branches.append({"type": "object", "additionalProperties": False,
                             "required": [identifier, "quote"], "properties": {
                                 identifier: {"type": "string", "enum": [key]},
                                 "quote": {"type": "string", "enum": choices}}})
    require(bool(branches), "Aucun passage suffisamment long à citer")
    return branches[0] if len(branches) == 1 else {"anyOf": branches}


def review_schema(documents, evidence):
    schema = copy.deepcopy(REVIEW_SCHEMA)
    fields = schema["properties"]["risks"]["items"]["properties"]
    fields["clause"] = reference_schema([(d["id"], d["text"]) for d in documents], "document_id", 10)
    fields["citations"]["items"] = reference_schema([(key, e.text) for key, e in evidence.items()], "evidence_id", 20)
    return schema
