"""Cabinet operations exercise the real contracts, RPC handlers and SQLite ledger."""
from datetime import date, datetime, timedelta, timezone
from hermes_cli import projects_db as pdb
from hermes_constants import set_hermes_home_override, reset_hermes_home_override
from tests.tui_gateway.test_legal_finance_rpc import call, denied, seed
from tui_gateway import server


def operations(pid):
    return call('legal.finance.snapshot',project_id=pid)['operations']


def test_collaborators_have_independent_timers_and_keep_owner_when_posting(tmp_path):
    pid,mid=seed(tmp_path)
    base=dict(project_id=pid,matter_id=mid,description='Travail attribué',rate_cents=20000,cost_rate_cents=8000)
    call('legal.finance.timer.start',**base,request_id='alice',responsible_user='alice')
    call('legal.finance.timer.start',**base,request_id='bob',responsible_user='bob')
    denied('legal.finance.timer.start',**base,request_id='alice-again',responsible_user='alice')
    denied('legal.finance.timer.start',**base,request_id='alice-spaces',responsible_user=' alice ')
    timer=next(t for t in operations(pid)['timers'] if t['responsible_user']=='alice')
    with pdb.connect_closing() as conn:
        conn.execute('UPDATE legal_time_trackers SET running_since=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=61)).isoformat(),timer['id']))
        conn.commit()
    call('legal.finance.timer.change',project_id=pid,request_id='pause-alice',timer_id=timer['id'],expected_version=1,command='pause')
    call('legal.finance.timer.change',project_id=pid,request_id='post-alice',timer_id=timer['id'],expected_version=2,command='finish')
    fee=call('legal.snapshot',project_id=pid)['fees'][0]
    assert fee['responsible_user']=='alice' and fee['minutes']==2 and fee['approval_status']=='draft'
    assert next(t for t in operations(pid)['timers'] if t['responsible_user']=='bob')['status']=='running'


def test_raw_transport_applies_declared_defaults_and_rejects_invalid_money(tmp_path):
    pid,_=seed(tmp_path)
    result=server._methods['legal.business.party.save'](1,{'project_id':pid,'request_id':'raw','name':'Tiers brut','role':'supplier'})
    assert 'error' not in result,result
    assert operations(pid)['parties'][0]['version']==1
    denied('legal.business.supplier_payment.add',project_id=pid,request_id='invalid',order_id='none',amount_cents=True,paid_on=date.today().isoformat(),reference='Refus')


def supplier(pid):
    call('legal.business.party.save',project_id=pid,request_id='supplier',name='Fournisseur de test',role='supplier')
    return operations(pid)['parties'][0]


def purchase(pid, sid):
    p=dict(project_id=pid,request_id='purchase',supplier_id=sid,reference='ACH-1',due_on=date.today().isoformat(),lines=[{'description':'Service cabinet','quantity_milli':1500,'unit_cents':1999,'tax_bps':2000}])
    call('legal.business.purchase.save',**p)
    call('legal.business.purchase.save',**p)
    return operations(pid)['purchases'][0]


def test_supplier_purchase_receipt_and_entered_payment(tmp_path):
    pid,_=seed(tmp_path);s=supplier(pid);order=purchase(pid,s['id'])
    assert len(operations(pid)['purchases'])==1
    assert order['net_cents']==2999 and order['tax_cents']==600 and order['total_cents']==3599
    assert operations(pid)['supplier_balance_cents']==0
    base=dict(project_id=pid,order_id=order['id'])
    denied('legal.business.supplier_payment.add',**base,request_id='early',amount_cents=100,paid_on=date.today().isoformat(),reference='Test')
    call('legal.business.purchase.transition',**base,request_id='order',expected_version=1,status='ordered')
    denied('legal.business.purchase.transition',**base,request_id='stale',expected_version=1,status='received')
    call('legal.business.purchase.transition',**base,request_id='receipt',expected_version=2,status='received')
    assert operations(pid)['supplier_balance_cents']==3599
    denied('legal.business.supplier_payment.add',**base,request_id='over',amount_cents=3600,paid_on=date.today().isoformat(),reference='Test')
    p={**base,'request_id':'pay','amount_cents':3599,'paid_on':date.today().isoformat(),'reference':'Saisie justificatif test'}
    call('legal.business.supplier_payment.add',**p);call('legal.business.supplier_payment.add',**p)
    call('legal.business.purchase.transition',**base,request_id='close',expected_version=3,status='closed')
    assert operations(pid)['supplier_balance_cents']==0
    assert len(operations(pid)['supplier_payments'])==1


def test_party_updates_are_versioned_and_do_not_break_purchase_links(tmp_path):
    pid,_=seed(tmp_path);s=supplier(pid);purchase(pid,s['id'])
    denied('legal.business.party.save',project_id=pid,request_id='role',id=s['id'],expected_version=1,name=s['name'],role='prospect')
    call('legal.business.party.save',project_id=pid,request_id='email',id=s['id'],expected_version=1,name=s['name'],role='supplier',email='test@example.invalid')
    assert operations(pid)['parties'][0]['version']==2
    denied('legal.business.party.save',project_id=pid,request_id='stale',id=s['id'],expected_version=1,name='Old',role='supplier')


def test_contract_dates_and_scope_are_checked(tmp_path):
    pid,_=seed(tmp_path);s=supplier(pid)
    base=dict(project_id=pid,party_id=s['id'],title='Maintenance test',start_on='2026-01-01',end_on='2026-12-31',amount_cents=120000)
    denied('legal.business.contract.save',**{**base,'start_on':'2027-01-01'},request_id='bad')
    call('legal.business.contract.save',**base,request_id='contract')
    row=operations(pid)['contracts'][0]
    call('legal.business.contract.save',**base,request_id='activate',id=row['id'],expected_version=1,status='active')
    assert operations(pid)['contracts'][0]['status']=='active'
    folder=tmp_path/'other';folder.mkdir()
    other=call('projects.create',name='Autre cabinet',folders=[str(folder)])['project']['id']
    denied('legal.business.contract.save',**{**base,'project_id':other},request_id='foreign')


def test_business_prepare_rolls_back_and_apply_is_idempotent(tmp_path):
    pid,_=seed(tmp_path)
    p=call('legal.finance.prepare',project_id=pid,request_id='prepared-party',action='business.party.save',payload={'name':'Prospect test','role':'prospect'})
    assert not operations(pid)['parties']
    call('legal.business.party.save',project_id=pid,**p['params'])
    call('legal.business.party.save',project_id=pid,**p['params'])
    assert len(operations(pid)['parties'])==1


def test_persistent_timer_pause_resume_and_single_conversion(tmp_path):
    pid,mid=seed(tmp_path)
    p=dict(project_id=pid,request_id='timer',matter_id=mid,description='Analyse chronométrée',rate_cents=12000,cost_rate_cents=6000)
    call('legal.finance.timer.start',**p);call('legal.finance.timer.start',**p)
    timer=operations(pid)['timers'][0]
    denied('legal.finance.timer.start',**{**p,'request_id':'another'})
    with pdb.connect_closing() as conn:
        conn.execute('UPDATE legal_time_trackers SET running_since=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(seconds=65)).isoformat(),timer['id']));conn.commit()
    base=dict(project_id=pid,timer_id=timer['id'])
    call('legal.finance.timer.change',**base,request_id='pause',expected_version=1,command='pause')
    assert 65<=operations(pid)['timers'][0]['seconds']<120
    prep=call('legal.finance.prepare',project_id=pid,request_id='convert',action='finance.timer.change',payload={'timer_id':timer['id'],'expected_version':2,'command':'finish'})
    assert not call('legal.snapshot',project_id=pid)['fees']
    call('legal.finance.timer.change',project_id=pid,**prep['params']);call('legal.finance.timer.change',project_id=pid,**prep['params'])
    fees=call('legal.snapshot',project_id=pid)['fees']
    assert len(fees)==1 and fees[0]['minutes']==2 and fees[0]['net_cents']==400 and fees[0]['cost_cents']==200
    assert fees[0]['approval_status']=='draft'
    denied('legal.finance.timer.change',**base,request_id='again',expected_version=3,command='finish')


def test_business_and_timers_remain_in_their_real_profile(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir()
    token=set_hermes_home_override(a)
    try:pid,mid=seed(a);supplier(pid)
    finally:reset_hermes_home_override(token)
    token=set_hermes_home_override(b)
    try:
        denied('legal.finance.snapshot',project_id=pid)
        other,_=seed(b)
        assert not operations(other)['parties']
    finally:reset_hermes_home_override(token)
    token=set_hermes_home_override(a)
    try:assert len(operations(pid)['parties'])==1
    finally:reset_hermes_home_override(token)
