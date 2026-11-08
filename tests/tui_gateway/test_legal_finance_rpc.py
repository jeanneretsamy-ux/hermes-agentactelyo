"""Real profile/SQLite/RPC tests for finance preparation, control and reporting."""
import csv
from datetime import date, timedelta
import io

from hermes_cli import projects_db as pdb
from hermes_constants import set_hermes_home_override, reset_hermes_home_override
from tui_gateway import server
from tui_gateway.contracts.registry import METHODS


def call(method, **params):
    spec=METHODS[method]
    result=server._methods[method](1,spec.params.model_validate(params).model_dump())
    assert 'error' not in result,result
    spec.result.model_validate(result['result'])
    return result['result']


def denied(method,**params):
    result=server._methods[method](1,params)
    assert 'error' in result,result


def seed(tmp_path, name='Client test'):
    pid=call('projects.create',name='Cabinet',folders=[str(tmp_path)])['project']['id']
    call('legal.workspace.set',project_id=pid,domain='social')
    call('legal.firm.settings.set',project_id=pid,legal_name='Cabinet test',address='Adresse cabinet',siren='123456789',vat_number='FR00123456789',vat_regime='standard',bar_name='Paris')
    client=call('legal.client.save',project_id=pid,name=name,address='Adresse client')['clients'][0]
    matter=call('legal.matter.save',project_id=pid,client_id=client['id'],title='Dossier',matter_type='Rupture du contrat')['matters'][0]
    return pid,matter['id']


def add(pid,mid,**extra):
    return call('legal.fee.add',project_id=pid,request_id=extra.pop('request_id','fee'),matter_id=mid,kind='time',minutes=30,rate_cents=20000,description='Appel',approval_status='draft',**extra)['fees'][-1]


def test_review_budget_costs_invoicing_and_payment_share_the_same_ledger(tmp_path):
    pid,mid=seed(tmp_path)
    fee=add(pid,mid,cost_rate_cents=8000)
    state=call('legal.finance.snapshot',project_id=pid)
    assert state['totals']['pending_cents']==10000
    assert state['totals']['cost_cents']==4000
    assert state['totals']['unbilled_cents']==0
    denied('legal.document.create',project_id=pid,request_id='unreviewed',matter_id=mid,kind='invoice',fee_ids=[fee['id']],due_on=date.today().isoformat())
    params=dict(project_id=pid,request_id='approve',fee_id=fee['id'],approval_status='approved',reason='Contrôle humain')
    call('legal.finance.fee.review',**params);call('legal.finance.fee.review',**params)
    assert call('legal.finance.snapshot',project_id=pid)['totals']['unbilled_cents']==10000
    invoice=call('legal.document.create',project_id=pid,request_id='invoice',matter_id=mid,kind='invoice',fee_ids=[fee['id']],due_on=date.today().isoformat())['documents'][0]
    call('legal.payment.add',project_id=pid,request_id='payment',document_id=invoice['id'],amount_cents=2000,paid_on=date.today().isoformat(),reference='Virement saisi')
    state=call('legal.finance.snapshot',project_id=pid)
    assert state['totals']['billed_net_cents']==10000
    assert state['totals']['margin_cents']==6000
    assert state['totals']['cash_received_cents']==2000
    assert state['totals']['outstanding_cents']==8000
    assert state['ageing']['not_due']==8000
    denied('legal.finance.fee.review',**{**params,'request_id':'change','approval_status':'rejected'})


def test_missing_costs_never_produce_a_fabricated_margin(tmp_path):
    pid,mid=seed(tmp_path);add(pid,mid)
    state=call('legal.finance.snapshot',project_id=pid)
    assert state['totals']['missing_costs']==1
    assert state['totals']['margin_cents'] is None


def test_zero_sales_rate_tracks_internal_nonbillable_work(tmp_path):
    pid,mid=seed(tmp_path)
    call('legal.fee.add',project_id=pid,request_id='internal',matter_id=mid,kind='time',description='Travail interne',minutes=15,rate_cents=0,billable=False,cost_rate_cents=8000)
    state=call('legal.finance.snapshot',project_id=pid)
    assert state['totals']['minutes']==15
    assert state['totals']['billable_minutes']==0
    assert state['totals']['cost_cents']==2000


def test_budget_retries_are_idempotent_and_stale_updates_are_rejected(tmp_path):
    pid,mid=seed(tmp_path)
    p=dict(project_id=pid,request_id='budget',matter_id=mid,expected_version=0,budget_minutes=20,revenue_cents=20000,cost_cents=3000)
    call('legal.finance.budget.save',**p);call('legal.finance.budget.save',**p)
    add(pid,mid,cost_rate_cents=8000)
    matter=call('legal.finance.snapshot',project_id=pid)['matters'][0]
    assert matter['budget']['version']==1
    assert matter['time_over_budget'] and matter['cost_over_budget']
    denied('legal.finance.budget.save',**{**p,'request_id':'stale','budget_minutes':999})
    assert call('legal.finance.snapshot',project_id=pid)['matters'][0]['budget']['budget_minutes']==20


def test_preparation_validates_the_real_operation_without_persisting_it(tmp_path):
    pid,mid=seed(tmp_path)
    payload=dict(matter_id=mid,description='Préparation',kind='fixed',amount_cents=5000,cost_cents=0,approval_status='draft')
    prepared=call('legal.finance.prepare',project_id=pid,action='fee.add',payload=payload,request_id='prepared-once')
    assert not call('legal.snapshot',project_id=pid)['fees']
    assert prepared['params']['amount_cents']==5000
    call('legal.fee.add',project_id=pid,**prepared['params'])
    call('legal.fee.add',project_id=pid,**prepared['params'])
    assert len(call('legal.snapshot',project_id=pid)['fees'])==1
    denied('legal.finance.prepare',project_id=pid,action='fee.add',payload={**payload,'project_id':'another'},request_id='bad-scope')


def test_invalid_cost_rolls_back_the_fee_and_idempotency_receipt(tmp_path):
    pid,mid=seed(tmp_path)
    denied('legal.fee.add',project_id=pid,request_id='bad-cost',matter_id=mid,description='Invalid',kind='fixed',amount_cents=5000,cost_cents=-1)
    assert not call('legal.snapshot',project_id=pid)['fees']


def test_ageing_uses_remaining_ttc_and_csv_neutralizes_formula_text(tmp_path):
    pid,mid=seed(tmp_path,name='=HYPERLINK("https://invalid")')
    fee=call('legal.fee.add',project_id=pid,request_id='approved-fee',matter_id=mid,kind='fixed',amount_cents=10000,cost_cents=0,description='Forfait')['fees'][0]
    invoice=call('legal.document.create',project_id=pid,request_id='invoice',matter_id=mid,kind='invoice',fee_ids=[fee['id']],due_on=date.today().isoformat())['documents'][0]
    with pdb.connect_closing() as conn:
        conn.execute('UPDATE legal_documents SET due_on=? WHERE id=?',((date.today()-timedelta(days=45)).isoformat(),invoice['id']));conn.commit()
    call('legal.payment.add',project_id=pid,request_id='partial',document_id=invoice['id'],amount_cents=2500,paid_on=date.today().isoformat(),reference='Partiel')
    assert call('legal.finance.snapshot',project_id=pid)['ageing']['days_31_60']==7500
    export=call('legal.finance.export',project_id=pid)
    row=list(csv.DictReader(io.StringIO(export['content'].lstrip('\ufeff')),delimiter=';'))[0]
    assert row['Client'].startswith("'=HYPERLINK")
    assert row['Encours TTC centimes']=='7500'


def test_finance_stays_in_its_on_disk_profile(tmp_path):
    first=tmp_path/'one';second=tmp_path/'two';first.mkdir();second.mkdir()
    token=set_hermes_home_override(first)
    try:pid,mid=seed(first);add(pid,mid)
    finally:reset_hermes_home_override(token)
    token=set_hermes_home_override(second)
    try:
        denied('legal.finance.snapshot',project_id=pid)
        other,_=seed(second)
        assert call('legal.finance.snapshot',project_id=other)['totals']['pending_cents']==0
    finally:reset_hermes_home_override(token)
    token=set_hermes_home_override(first)
    try:assert call('legal.finance.snapshot',project_id=pid)['totals']['pending_cents']==10000
    finally:reset_hermes_home_override(token)
