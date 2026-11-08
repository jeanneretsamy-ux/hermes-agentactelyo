"""Wire contracts for the cabinet's CRM, purchasing and persistent timers."""
from typing import Literal
from pydantic import Field
from .base import Result
from .legal_practice import LegalProjectParams, LegalSnapshot
from .registry import method


class BusinessRecord(Result):
    id: str
    project_id: str


class BusinessParty(BusinessRecord):
    name: str
    role: Literal['prospect','supplier','partner']
    email: str
    phone: str
    address: str
    notes: str
    version: int


class BusinessContract(BusinessRecord):
    party_id: str
    title: str
    start_on: str
    end_on: str
    amount_cents: int
    status: Literal['draft','active','closed']
    version: int


class PurchaseLine(Result):
    description: str = Field(min_length=1,max_length=1000)
    quantity_milli: int = Field(default=1000,ge=1,le=1_000_000,strict=True)
    unit_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    tax_bps: int = Field(default=0,ge=0,le=10000,strict=True)


class PurchaseLineResult(PurchaseLine):
    net_cents: int
    tax_cents: int


class PurchaseOrder(BusinessRecord):
    supplier_id: str
    reference: str
    due_on: str
    lines: list[PurchaseLineResult]
    net_cents: int
    tax_cents: int
    total_cents: int
    status: Literal['draft','ordered','received','closed','cancelled']
    version: int
    paid_cents: int
    balance_cents: int


class SupplierPayment(BusinessRecord):
    order_id: str
    amount_cents: int
    paid_on: str
    reference: str


class TimeTracker(BusinessRecord):
    responsible_user: str
    matter_id: str
    description: str
    rate_cents: int
    cost_rate_cents: int | None
    billable: int
    seconds: int
    running_since: str | None
    status: Literal['running','paused','finished']
    version: int
    elapsed_seconds: int


class AccountingImport(BusinessRecord):
    filename: str
    digest: str
    imported_on: str
    row_count: int
    debit_cents: int
    credit_cents: int
    revenue_cents: int
    expense_cents: int
    matched_references: list[str]
    unmatched_references: list[str]


class FinancialObjective(BusinessRecord):
    responsible_user: str
    role: Literal['collaborator','partner']
    start_on: str
    end_on: str
    revenue_cents: int
    margin_cents: int
    minutes: int
    version: int
    actual_minutes: int
    production_cents: int
    missing_costs: int
    production_margin_cents: int | None


class FinancialForecast(BusinessRecord):
    month: str
    label: str
    incoming_cents: int
    outgoing_cents: int
    version: int


class MileageRecord(BusinessRecord):
    matter_id: str
    activity_date: str
    responsible_user: str
    route: str
    distance_milli: int
    rate_cents: int
    rate_source: str
    amount_cents: int
    fee_id: str


class ReminderDraft(BusinessRecord):
    document_id: str
    level: int
    created_on: str
    balance_cents: int
    content: str
    status: Literal['draft']


class FinancialControls(Result):
    imports: list[AccountingImport]
    objectives: list[FinancialObjective]
    forecasts: list[FinancialForecast]
    mileage: list[MileageRecord]
    reminders: list[ReminderDraft]


class BillingOrderLine(Result):
    id: str
    description: str
    kind: str
    minutes: int
    rate_cents: int
    net_cents: int
    tax_bps: int
    tax_cents: int
    responsible_user: str
    activity_date: str


class BillingOrder(BusinessRecord):
    matter_id: str
    reference: str
    created_on: str
    purpose: str
    fee_ids: list[str]
    source_digest: str
    lines: list[BillingOrderLine]
    net_cents: int
    tax_cents: int
    total_cents: int
    status: Literal['ready','invoiced','cancelled']
    document_id: str | None
    version: int


class FinanceFile(BusinessRecord):
    matter_id: str
    filename: str
    kind: Literal['financial_statement','financial_document','evidence','ocr_result']
    size_bytes: int
    sha256: str
    created_on: str
    source_file_id: str | None
    piece_number: int
    extraction_mode: Literal['not_requested','text','partial_text','ocr','partial_ocr']
    extraction_source_id: str | None


class CabinetOperations(Result):
    files: list[FinanceFile]
    billing_orders: list[BillingOrder]
    controls: FinancialControls
    parties: list[BusinessParty]
    contracts: list[BusinessContract]
    purchases: list[PurchaseOrder]
    supplier_payments: list[SupplierPayment]
    timers: list[TimeTracker]
    supplier_balance_cents: int
    scope: str


class BusinessMutation(LegalProjectParams):
    request_id: str = Field(min_length=1,max_length=100)


class PartyParams(BusinessMutation):
    id: str | None = None
    expected_version: int = Field(default=0,ge=0,le=1_000_000,strict=True)
    name: str = Field(min_length=1,max_length=200)
    role: Literal['prospect','supplier','partner']
    email: str = Field(default='',max_length=320)
    phone: str = Field(default='',max_length=100)
    address: str = Field(default='',max_length=2000)
    notes: str = Field(default='',max_length=4000)


class ContractParams(BusinessMutation):
    id: str | None = None
    expected_version: int = Field(default=0,ge=0,le=1_000_000,strict=True)
    party_id: str
    title: str = Field(min_length=1,max_length=1000)
    start_on: str
    end_on: str
    amount_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    status: Literal['draft','active','closed'] = 'draft'


class PurchaseParams(BusinessMutation):
    supplier_id: str
    reference: str = Field(min_length=1,max_length=100)
    due_on: str
    lines: list[PurchaseLine] = Field(min_length=1,max_length=100)


class PurchaseTransitionParams(BusinessMutation):
    order_id: str
    expected_version: int = Field(ge=1,le=1_000_000,strict=True)
    status: Literal['ordered','received','closed','cancelled']


class SupplierPaymentParams(BusinessMutation):
    order_id: str
    amount_cents: int = Field(ge=1,le=1_000_000_000,strict=True)
    paid_on: str
    reference: str = Field(min_length=1,max_length=1000)


class TimerStartParams(BusinessMutation):
    responsible_user: str = Field(default="",max_length=200)
    matter_id: str
    description: str = Field(min_length=1,max_length=1000)
    rate_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    cost_rate_cents: int | None = Field(default=None,ge=0,le=1_000_000_000,strict=True)
    billable: bool = True


class TimerChangeParams(BusinessMutation):
    timer_id: str
    expected_version: int = Field(ge=1,le=1_000_000,strict=True)
    command: Literal['pause','resume','finish']


class FecImportParams(BusinessMutation):
    filename: str = Field(min_length=1,max_length=200)
    content: str = Field(min_length=1,max_length=60000)


class ObjectiveParams(BusinessMutation):
    responsible_user: str = Field(min_length=1,max_length=200)
    role: Literal['collaborator','partner']
    start_on: str
    end_on: str
    revenue_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    margin_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    minutes: int = Field(ge=0,le=1_000_000,strict=True)
    expected_version: int = Field(default=0,ge=0,le=1_000_000,strict=True)


class ForecastParams(BusinessMutation):
    month: str = Field(min_length=7,max_length=7)
    label: str = Field(min_length=1,max_length=200)
    incoming_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    outgoing_cents: int = Field(ge=0,le=1_000_000_000,strict=True)
    expected_version: int = Field(default=0,ge=0,le=1_000_000,strict=True)


class MileageParams(BusinessMutation):
    matter_id: str
    activity_date: str
    responsible_user: str = Field(min_length=1,max_length=200)
    route: str = Field(min_length=1,max_length=1000)
    distance_milli: int = Field(ge=1,le=1_000_000_000,strict=True)
    rate_cents: int = Field(ge=1,le=100000,strict=True)
    rate_source: str = Field(min_length=1,max_length=1000)
    billable: bool = False


class ReminderParams(BusinessMutation):
    document_id: str
    level: int = Field(ge=1,le=3,strict=True)
    message: str = Field(min_length=1,max_length=4000)


class BillingOrderCreateParams(BusinessMutation):
    matter_id: str
    fee_ids: list[str] = Field(min_length=1,max_length=500)
    purpose: Literal['standard','provision_fees','provision_expenses','provision_expenses_fees'] = 'standard'


class BillingOrderChangeParams(BusinessMutation):
    billing_order_id: str
    expected_version: int = Field(ge=1,le=1_000_000,strict=True)


class BillingOrderInvoiceParams(BillingOrderChangeParams):
    due_on: str
    template_id: Literal['classique','synthese','detaille'] = 'classique'


class FileMutationParams(BusinessMutation):
    file_id: str


class FileStampParams(FileMutationParams):
    piece_number: int = Field(ge=1,le=999999,strict=True)


BUSINESS_ACTIONS = {
    'finance.file.extract':FileMutationParams,'finance.file.stamp':FileStampParams,
    'finance.billing_order.create':BillingOrderCreateParams,
    'finance.billing_order.invoice':BillingOrderInvoiceParams,
    'finance.billing_order.cancel':BillingOrderChangeParams,
    'finance.fec.import':FecImportParams,'finance.objective.save':ObjectiveParams,
    'finance.forecast.save':ForecastParams,'finance.mileage.add':MileageParams,
    'finance.reminder.prepare':ReminderParams,
    'business.party.save':PartyParams,'business.contract.save':ContractParams,
    'business.purchase.save':PurchaseParams,'business.purchase.transition':PurchaseTransitionParams,
    'business.supplier_payment.add':SupplierPaymentParams,
    'finance.timer.start':TimerStartParams,'finance.timer.change':TimerChangeParams,
}
for action, params in BUSINESS_ACTIONS.items():
    method('legal.'+action,params=params,result=LegalSnapshot)


class FileStartParams(BusinessMutation):
    matter_id: str
    filename: str = Field(min_length=1,max_length=200)
    kind: Literal['financial_statement','financial_document','evidence','ocr_result']
    size_bytes: int = Field(ge=1,le=5_000_000,strict=True)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class FileUploadParams(LegalProjectParams):
    upload_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class FileChunkParams(FileUploadParams):
    sequence: int = Field(ge=0,le=138,strict=True)
    data_base64: str = Field(min_length=1,max_length=48000)


class FileReadParams(LegalProjectParams):
    file_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    offset: int = Field(ge=0,le=5_000_000,strict=True)


class FileTextParams(LegalProjectParams):
    file_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class FileStartResult(Result):
    upload_id: str
    chunk_bytes: int


class FileChunkResult(Result):
    upload_id: str
    sequence: int
    accepted_bytes: int


class FileCancelResult(Result):
    upload_id: str
    cancelled: bool


class FileReadResult(Result):
    file_id: str
    offset: int
    data_base64: str
    size_bytes: int
    sha256: str
    filename: str


class FileTextResult(Result):
    file_id: str
    sha256: str
    text: str
    mode: str
    untrusted: Literal[True]
    extraction_source_id: str | None


FILE_METHODS={
    'finance.file.start':(FileStartParams,FileStartResult),
    'finance.file.chunk':(FileChunkParams,FileChunkResult),
    'finance.file.finish':(FileUploadParams,FinanceFile),
    'finance.file.cancel':(FileUploadParams,FileCancelResult),
    'finance.file.read':(FileReadParams,FileReadResult),
    'finance.file.text':(FileTextParams,FileTextResult),
}
for action,(params,result) in FILE_METHODS.items():
    method('legal.'+action,params=params,result=result)
