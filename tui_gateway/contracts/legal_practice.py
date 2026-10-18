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


class LegalWorkspaceEntry(Result):
    id: str
    name: str
    domain: str | None


class LegalCatalog(Result):
    domains: list[LegalDomain]
    workspaces: list[LegalWorkspaceEntry]


class LegalClientSnapshot(Result):
    name: str
    email: str
    address: str
    customer_type: Literal["individual", "professional"] = "individual"
    siren: str = ""


class LegalClient(LegalClientSnapshot):
    id: str


class LegalMatterSnapshot(Result):
    title: str
    reference: str
    matter_type: str = ""
    matter_profile: dict[str, dict[str, str]] = Field(default_factory=dict)
    company_profile: dict[str, dict[str, str]] = Field(default_factory=dict)


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
    kind: Literal["fixed", "time", "expense"]
    minutes: int
    rate_cents: int
    invoice_id: str | None
    responsible_user: str = ""
    activity_date: str
    billing_code: str
    activity_type: str
    billable: bool


class LegalFeeCode(Result):
    id: str
    code: str
    label: str
    hourly_rate_cents: int
    fixed_amount_cents: int
    tax_bps: int


class LegalSubscription(Result):
    id: str
    matter_id: str
    label: str
    amount_cents: int
    tax_bps: int
    cadence: Literal["monthly", "semiannual", "annual"]
    starts_on: str
    ends_on: str
    next_invoice_on: str
    status: Literal["active", "paused", "ended"]


class LegalFirmSettings(Result):
    jurisdiction: str
    legal_name: str
    address: str
    siren: str
    vat_number: str
    vat_regime: Literal["standard", "franchise"]
    bar_name: str
    payment_delay_days: int
    late_penalty_rate: str


class LegalInvoiceIssuer(Result):
    legal_name: str
    address: str
    siren: str
    vat_number: str
    vat_regime: Literal["standard", "franchise"]
    bar_name: str


class LegalBillingGroup(Result):
    user: str
    fees_cents: int
    fee_count: int


class LegalProjectBillingGroup(Result):
    project_id: str
    name: str
    fees_cents: int
    fee_count: int


class LegalMatterBillingGroup(Result):
    project_id: str
    project: str
    matter_id: str
    title: str
    fees_cents: int
    fee_count: int


class LegalFirmTotals(Result):
    fees_cents: int
    fee_count: int
    invoiced_cents: int
    paid_cents: int
    balance_cents: int
    by_project: list[LegalProjectBillingGroup]
    by_user: list[LegalBillingGroup]
    by_matter: list[LegalMatterBillingGroup]


class LegalDocumentSnapshot(Result):
    client: LegalClientSnapshot
    matter: LegalMatterSnapshot
    lines: list[LegalLine]
    jurisdiction: str | None = None
    issuer: LegalInvoiceIssuer | None = None
    payment_terms: dict[str, object] | None = None
    vat_notice: str = ""
    template_id: Literal["classique", "synthese", "detaille"] = "classique"
    purpose: str = "standard"
    credited_invoice_reference: str | None = None
    credit_reason: str | None = None


class LegalDocument(Result):
    id: str
    matter_id: str
    kind: Literal["quote", "invoice", "credit_note"]
    reference: str
    created_on: str
    due_on: str
    snapshot: LegalDocumentSnapshot
    net_cents: int
    tax_cents: int
    total_cents: int
    paid_cents: int
    balance_cents: int
    credited_cents: int = 0
    cancelled: bool = False
    refund_due_cents: int = 0
    purpose: str = "standard"
    related_document_id: str | None = None
    rendered_document: str


class LegalPayment(Result):
    id: str
    document_id: str
    amount_cents: int
    paid_on: str
    reference: str


class LegalPracticeDocumentTemplate(Result):
    id: str
    label: str


class LegalPracticeDocument(Result):
    id: str
    matter_id: str
    template_id: str
    title: str
    body: str
    fee_ids: list[str]
    created_on: str


class LegalCompanyProfileField(Result):
    id: str
    label: str


class LegalCompanyProfileSection(Result):
    id: str
    label: str
    fields: list[LegalCompanyProfileField]


class LegalSnapshot(Result):
    project_id: str
    domain: str | None
    matter_types: list[str]
    domains: list[LegalDomain]
    matter_profile_schema: list[LegalCompanyProfileSection]
    company_profile_schema: list[LegalCompanyProfileSection]
    clients: list[LegalClient]
    matters: list[LegalMatter]
    acts: list[LegalAct]
    fees: list[LegalFee]
    fee_codes: list[LegalFeeCode]
    subscriptions: list[LegalSubscription]
    practice_documents: list[LegalPracticeDocument]
    practice_document_templates: list[LegalPracticeDocumentTemplate]
    documents: list[LegalDocument]
    payments: list[LegalPayment]
    firm_settings: LegalFirmSettings
    firm_totals: LegalFirmTotals


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
    customer_type: Literal["individual", "professional"] = "individual"
    siren: str = ""


class LegalMatterParams(LegalProjectParams):
    id: str | None = None
    client_id: str
    title: str
    matter_type: str
    reference: str = ""
    status: Literal["open", "closed"] = "open"
    matter_profile: dict[str, dict[str, str]] | None = None
    company_profile: dict[str, dict[str, str]] | None = None


class LegalActParams(LegalProjectParams):
    id: str | None = None
    title: str
    act_type: str
    body: str


class LegalLibraryEntry(Result):
    title: str = Field(min_length=1, max_length=500)
    act_type: str = Field(min_length=1, max_length=100)
    body: str = Field(min_length=1, max_length=200_000)


class LegalLibraryImportParams(LegalProjectParams):
    domain: str
    entries: list[LegalLibraryEntry] = Field(min_length=1, max_length=500)


class LegalFeeParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    matter_id: str
    description: str
    kind: Literal["fixed", "time", "expense"]
    amount_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    minutes: int = Field(default=0, ge=0, le=1_000_000, strict=True)
    rate_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    tax_bps: int = Field(default=0, ge=0, le=10000, strict=True)
    responsible_user: str = ""
    activity_date: str = ""
    billing_code: str = ""
    activity_type: str = ""
    billable: bool = True


class LegalFeeCodeParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    id: str | None = None
    code: str
    label: str
    hourly_rate_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    fixed_amount_cents: int = Field(default=0, ge=0, le=1_000_000_000, strict=True)
    tax_bps: int = Field(default=0, ge=0, le=10000, strict=True)


class LegalSubscriptionParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    id: str | None = None
    matter_id: str
    label: str
    amount_cents: int = Field(ge=1, le=1_000_000_000, strict=True)
    tax_bps: int = Field(default=0, ge=0, le=10000, strict=True)
    cadence: Literal["monthly", "semiannual", "annual"]
    starts_on: str
    ends_on: str = ""
    next_invoice_on: str = ""
    status: Literal["active", "paused", "ended"] = "active"


class LegalSubscriptionInvoiceParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    subscription_id: str
    template_id: Literal["classique", "synthese", "detaille"] = "classique"


class LegalPracticeDocumentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    matter_id: str
    template_id: str
    title: str = ""
    fee_ids: list[str] = Field(default_factory=list, max_length=500)


class LegalFirmSettingsParams(LegalProjectParams):
    jurisdiction: Literal["FR"] = "FR"
    legal_name: str
    address: str
    siren: str
    vat_number: str = ""
    vat_regime: Literal["standard", "franchise"] = "standard"
    bar_name: str = ""
    payment_delay_days: int = Field(default=30, ge=1, le=60, strict=True)
    late_penalty_rate: str = "3 fois le taux d’intérêt légal"


class LegalDocumentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    matter_id: str
    kind: Literal["quote", "invoice"]
    fee_ids: list[str] = Field(min_length=1, max_length=500)
    due_on: str
    template_id: Literal["classique", "synthese", "detaille"] = "classique"
    purpose: Literal["standard", "provision_fees", "provision_expenses_fees"] = "standard"


class LegalCreditParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    document_id: str
    reason: str = Field(min_length=1, max_length=500)


class LegalPaymentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    document_id: str
    amount_cents: int = Field(ge=1, le=1_000_000_000, strict=True)
    paid_on: str
    reference: str


class LegalPaymentAllocation(Result):
    document_id: str
    amount_cents: int = Field(ge=1, le=1_000_000_000, strict=True)


class LegalAllocatePaymentParams(LegalProjectParams):
    request_id: str = Field(min_length=1, max_length=100)
    amount_cents: int = Field(ge=1, le=1_000_000_000, strict=True)
    paid_on: str
    reference: str
    allocations: list[LegalPaymentAllocation] = Field(min_length=1, max_length=100)


method("legal.catalog", params=ProfileParams, result=LegalCatalog)
method("legal.snapshot", params=LegalProjectParams, result=LegalSnapshot)
method("legal.workspace.set", params=LegalWorkspaceParams, result=LegalSnapshot)
method("legal.firm.settings.set", params=LegalFirmSettingsParams, result=LegalSnapshot)
method("legal.client.save", params=LegalClientParams, result=LegalSnapshot)
method("legal.matter.save", params=LegalMatterParams, result=LegalSnapshot)
method("legal.act.save", params=LegalActParams, result=LegalSnapshot)
method("legal.library.import", params=LegalLibraryImportParams, result=LegalSnapshot)
method("legal.fee.add", params=LegalFeeParams, result=LegalSnapshot)
method("legal.fee_code.save", params=LegalFeeCodeParams, result=LegalSnapshot)
method("legal.subscription.save", params=LegalSubscriptionParams, result=LegalSnapshot)
method("legal.subscription.invoice", params=LegalSubscriptionInvoiceParams, result=LegalSnapshot)
method("legal.practice_document.create", params=LegalPracticeDocumentParams, result=LegalSnapshot)
method("legal.document.create", params=LegalDocumentParams, result=LegalSnapshot)
method("legal.document.credit", params=LegalCreditParams, result=LegalSnapshot)
method("legal.payment.add", params=LegalPaymentParams, result=LegalSnapshot)
method("legal.payment.allocate", params=LegalAllocatePaymentParams, result=LegalSnapshot)
