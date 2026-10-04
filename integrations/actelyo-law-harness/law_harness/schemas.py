"""Schemas shared by prompts and constrained model generation."""
import copy
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


def review_schema(documents, evidence):
    schema = copy.deepcopy(REVIEW_SCHEMA)
    fields = schema["properties"]["risks"]["items"]["properties"]
    fields["clause"]["properties"]["document_id"] = {
        "type": "string", "enum": [d["id"] for d in documents]}
    fields["citations"]["items"]["properties"]["evidence_id"] = {
        "type": "string", "enum": list(evidence)}
    return schema
