"""Project-owned legal workspaces and internal draft billing."""
from typing import Literal

from pydantic import Field

from .base import Result
from .common import ProfileParams
from .registry import method


class LegalDomain(Result):
    id: str
    label: str
    matter_types: list[str]
    act_types: list[str]


class LegalClientSnapshot(Result):
    name: str
    email: str
    address: str


class LegalClient(LegalClientSnapshot):
    id: str


class LegalMatterSnapshot(Result):
    title: str
    reference: str


class LegalMatter(LegalMatterSnapshot):
    id: str
    client_id: str
    matter_type: str
    status: Literal["open", "closed"]


class LegalAct(Result):
    id: str
    title: str
    act_type: str
    body: str


class LegalLine(Result):
    description: str
    net_cents: int
    tax_bps: int
    tax_cents: int


class LegalFee(LegalLine):
    id: str
    matter_id: str
    kind: Literal["fixed", "time"]
    minutes: int
    rate_cents: int
    invoice_id: str | None


class LegalDocumentSnapshot(Result):
    client: LegalClientSnapshot
    matter: LegalMatterSnapshot
    lines: list[LegalLine]


class LegalDocument(Result):
    id: str
    matter_id: str
    kind: Literal["quote", "invoice"]
    reference: str
    created_on: str
    due_on: str
    snapshot: LegalDocumentSnapshot
    net_cents: int
    tax_cents: int
    total_cents: int
    paid_cents: int
    balance_cents: int


class LegalPayment(Result):
    id: str
    document_id: str
    amount_cents: int
    paid_on: str
    reference: str


class LegalSnapshot(Result):
    project_id: str
    domain: str | None
    matter_types: list[str]
    domains: list[LegalDomain]
    clients: list[LegalClient]
    matters: list[LegalMatter]
    acts: list[LegalAct]
    fees: list[LegalFee]
    documents: list[LegalDocument]
    payments: list[LegalPayment]


class LegalProjectParams(ProfileParams):
    project_id: str = Field(min_length=1)


class LegalWorkspaceParams(LegalProjectParams):
    domain: str
    matter_types: list[str] | None = None


class LegalClientParams(LegalProjectParams):
    id: str | None = None
    name: str
    email: str = ""
    address: str = ""


class LegalMatterParams(LegalProjectParams):
    id: str | None = None
    client_id: str
    title: str
    matter_type: str
    reference: str = ""
    status: Literal["open", "closed"] = "open"


class LegalActParams(LegalProjectParams):
    id: str | None = None
    title: str
    act_type: str
    body: str


class LegalFeeParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    matter_id: str
    description: str
    kind: Literal["fixed", "time"]
    amount_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    minutes: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    rate_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    tax_bps: int = Field(default=0, ge=0, le=10000, strict=True)


class LegalDocumentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    matter_id: str
    kind: Literal["quote", "invoice"]
    fee_ids: list[str] = Field(min_length=1, max_length=500)
    due_on: str


class LegalPaymentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    document_id: str
    amount_cents: int = Field(ge=1, le=1_000_000_000, strict=True)
    paid_on: str
    reference: str


method("legal.snapshot", params=LegalProjectParams, result=LegalSnapshot)
method("legal.workspace.set", params=LegalWorkspaceParams, result=LegalSnapshot)
method("legal.client.save", params=LegalClientParams, result=LegalSnapshot)
method("legal.matter.save", params=LegalMatterParams, result=LegalSnapshot)
method("legal.act.save", params=LegalActParams, result=LegalSnapshot)
method("legal.fee.add", params=LegalFeeParams, result=LegalSnapshot)
method("legal.document.create", params=LegalDocumentParams, result=LegalSnapshot)
method("legal.payment.add", params=LegalPaymentParams, result=LegalSnapshot)
