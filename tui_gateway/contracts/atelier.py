"""Data-only creator panels, shared by Desktop and the agent CLI."""
from typing import Literal
from .base import JsonValue, Result
from .common import ProfileParams
from .registry import method


class AtelierRevision(Result):
    id: str
    name: str
    revision: str
    created_at: str
    active: bool


class AtelierSnapshot(Result):
    revisions: list[AtelierRevision]


class AtelierEvidence(Result):
    passage_id: str
    source_id: str
    document_id: str
    name: str
    url: str
    page: int | None
    start: int
    end: int
    offset_scope: str
    source_sha256: str
    quote: str
    table: JsonValue = None


class AtelierEvent(Result):
    id: str
    date: str
    title: str
    evidence: list[AtelierEvidence]


class AtelierPanel(Result):
    id: str
    name: str
    kind: Literal['chronology']
    revision: str
    events: list[AtelierEvent]
    source_binding: Literal['verified']
    semantic_review: Literal['human_required']


class AtelierRevisionParams(ProfileParams):
    revision: str


class AtelierDeactivateParams(ProfileParams):
    panel_id: str


method('atelier.list', params=ProfileParams, result=AtelierSnapshot)
method('atelier.preview', params=AtelierRevisionParams, result=AtelierPanel)
method('atelier.activate', params=AtelierRevisionParams, result=AtelierSnapshot)
method('atelier.deactivate', params=AtelierDeactivateParams, result=AtelierSnapshot)
