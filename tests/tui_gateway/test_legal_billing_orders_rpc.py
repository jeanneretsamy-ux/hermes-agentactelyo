"""Billing approvals use the same contracts, profile-owned ledger and invoice workflow."""
from datetime import date
from hermes_cli import projects_db as pdb
from tests.tui_gateway.test_legal_finance_rpc import call,denied,seed


def orders(pid): return call('legal.finance.snapshot',project_id=pid)['operations']['billing_orders']


def fee(pid,mid,request='fee'):
    result=call('legal.fee.add',project_id=pid,request_id=request,matter_id=mid,kind='fixed',description='Rédaction',amount_cents=10000,tax_bps=2000,cost_cents=4000)
    return next(f for f in result['fees'] if f['description']=='Rédaction')


def test_billing_order_reserves_approved_fees_only_after_confirmation_and_invoices_once(tmp_path):
    pid,mid=seed(tmp_path);f=fee(pid,mid)
    prepared=call('legal.finance.prepare',project_id=pid,request_id='baf',action='finance.billing_order.create',payload={'matter_id':mid,'fee_ids':[f['id']]})
    assert not orders(pid)
    call('legal.finance.billing_order.create',project_id=pid,**prepared['params'])
    call('legal.finance.billing_order.create',project_id=pid,**prepared['params'])
    order=orders(pid)[0]
    assert len(orders(pid))==1 and order['net_cents']==10000 and order['total_cents']==12000
    assert order['lines'][0]['id']==f['id'] and order['reference'].startswith('BAF-')
    denied('legal.finance.billing_order.create',project_id=pid,request_id='duplicate',matter_id=mid,fee_ids=[f['id']])
    denied('legal.document.create',project_id=pid,request_id='bypass',matter_id=mid,kind='invoice',fee_ids=[f['id']],due_on=date.today().isoformat())
    params=dict(project_id=pid,request_id='invoice',billing_order_id=order['id'],expected_version=1,due_on=date.today().isoformat())
    call('legal.finance.billing_order.invoice',**params);call('legal.finance.billing_order.invoice',**params)
    state=call('legal.snapshot',project_id=pid)
    assert len(state['documents'])==1
    assert orders(pid)[0]['document_id']==state['documents'][0]['id']
    assert orders(pid)[0]['status']=='invoiced'
    denied('legal.finance.billing_order.cancel',project_id=pid,request_id='cancel-invoiced',billing_order_id=order['id'],expected_version=2)


def test_changed_fee_approval_and_price_never_silently_change_the_frozen_order(tmp_path):
    pid,mid=seed(tmp_path);f=fee(pid,mid)
    call('legal.finance.billing_order.create',project_id=pid,request_id='order',matter_id=mid,fee_ids=[f['id']])
    order=orders(pid)[0]
    with pdb.connect_closing() as conn:
        conn.execute('UPDATE legal_fees SET net_cents=99999 WHERE id=?',(f['id'],));conn.commit()
    denied('legal.finance.billing_order.invoice',project_id=pid,request_id='changed',billing_order_id=order['id'],expected_version=1,due_on=date.today().isoformat())
    assert orders(pid)[0]['net_cents']==10000
    assert not call('legal.snapshot',project_id=pid)['documents']
    call('legal.finance.billing_order.cancel',project_id=pid,request_id='cancel',billing_order_id=order['id'],expected_version=1)
    assert orders(pid)[0]['status']=='cancelled'
    call('legal.finance.billing_order.create',project_id=pid,request_id='new',matter_id=mid,fee_ids=[f['id']])
    assert orders(pid)[0]['reference']!=order['reference']


def test_unapproved_nonbillable_foreign_and_mixed_provision_lines_are_rejected(tmp_path):
    pid,mid=seed(tmp_path);f=fee(pid,mid)
    denied('legal.finance.billing_order.create',project_id=pid,request_id='wrong',matter_id=mid,fee_ids=[f['id']],purpose='provision_expenses')
    call('legal.finance.fee.review',project_id=pid,request_id='draft',fee_id=f['id'],approval_status='draft',reason='Contrôle en cours')
    denied('legal.finance.billing_order.create',project_id=pid,request_id='unreviewed',matter_id=mid,fee_ids=[f['id']])
    assert not orders(pid)
