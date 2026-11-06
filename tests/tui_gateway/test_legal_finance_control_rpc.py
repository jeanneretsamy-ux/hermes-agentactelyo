"""Accounting and forecasts through real RPC, contracts and profile-owned SQLite."""
from datetime import date, timedelta
from hermes_constants import set_hermes_home_override, reset_hermes_home_override
from tests.tui_gateway.test_legal_finance_rpc import call, denied, seed
from hermes_cli.legal_finance_control import FEC_FIELDS


def fec(reference='VENTE-TEST'):
    head='|'.join(FEC_FIELDS)
    rows=[['VE','Ventes','1','20260102','411000','Client','','',reference,'20260102','Honoraires','120,00','0,00','','','20260102','',''],
          ['VE','Ventes','1','20260102','706000','Honoraires','','',reference,'20260102','Honoraires','0,00','100,00','','','20260102','',''],
          ['VE','Ventes','1','20260102','445710','TVA','','',reference,'20260102','TVA','0,00','20,00','','','20260102','','']]
    return head+'\n'+'\n'.join('|'.join(r) for r in rows)


def controls(pid):
    return call('legal.finance.snapshot',project_id=pid)['operations']['controls']


def test_fec_preview_is_readonly_commit_deduplicates_and_does_not_issue_invoices(tmp_path):
    pid,_=seed(tmp_path)
    payload={'filename':'comptabilite.txt','content':fec()}
    preparation=call('legal.finance.prepare',project_id=pid,request_id='preview',action='finance.fec.import',payload=payload)
    assert not controls(pid)['imports']
    params=preparation['params']
    call('legal.finance.fec.import',project_id=pid,**params)
    call('legal.finance.fec.import',project_id=pid,**params)
    sources=controls(pid)['imports']
    assert len(sources)==1 and sources[0]['debit_cents']==sources[0]['credit_cents']==12000
    assert sources[0]['revenue_cents']==10000
    assert sources[0]['unmatched_references']==['VENTE-TEST']
    assert not call('legal.snapshot',project_id=pid)['documents']
    denied('legal.finance.fec.import',project_id=pid,request_id='again',filename='autre.txt',content='\ufeff'+fec().replace('\n','\r\n'))
    denied('legal.finance.fec.import',project_id=pid,request_id='overlap',filename='copie.txt',content=fec('AUTRE-REF'))


def test_fec_rejects_unbalanced_entries_dates_and_multicurrency(tmp_path):
    pid,_=seed(tmp_path)
    for n,content in enumerate([fec().replace('120,00','119,00'),fec().replace('20260102','20260230'),fec().replace('20260102||','20260102|1|USD'),fec().replace('JournalCode','Wrong')]):
        denied('legal.finance.fec.import',project_id=pid,request_id=f'invalid-{n}',filename='refus.txt',content=content)
    assert not controls(pid)['imports']


def test_expense_only_provision_has_its_own_purpose_and_rejects_honorarium_lines(tmp_path):
    pid,mid=seed(tmp_path)
    expense=call('legal.fee.add',project_id=pid,request_id='expense',matter_id=mid,kind='expense',description='Frais',expense_type='office',amount_cents=5000,cost_cents=5000)['fees'][0]
    denied('legal.document.create',project_id=pid,request_id='wrong-purpose',matter_id=mid,kind='invoice',purpose='provision_fees',fee_ids=[expense['id']],due_on=date.today().isoformat())
    document=call('legal.document.create',project_id=pid,request_id='expense-provision',matter_id=mid,kind='invoice',purpose='provision_expenses',fee_ids=[expense['id']],due_on=date.today().isoformat())['documents'][0]
    assert document['purpose']=='provision_expenses' and document['total_cents']==5000
    assert 'Facture de provision sur frais' in document['rendered_document']


def test_goals_and_forecasts_have_versions_and_measured_costs(tmp_path):
    pid,mid=seed(tmp_path);today=date.today().isoformat()
    call('legal.fee.add',project_id=pid,request_id='work',matter_id=mid,kind='time',description='Analyse',minutes=60,rate_cents=20000,cost_rate_cents=8000,responsible_user='alice',activity_date=today)
    p=dict(project_id=pid,request_id='goal',responsible_user='alice',role='partner',start_on=today,end_on=today,revenue_cents=30000,margin_cents=10000,minutes=120)
    call('legal.finance.objective.save',**p)
    goal=controls(pid)['objectives'][0]
    assert goal['actual_minutes']==60 and goal['production_cents']==20000 and goal['production_margin_cents']==12000
    denied('legal.finance.objective.save',**{**p,'request_id':'stale'})
    call('legal.finance.forecast.save',project_id=pid,request_id='forecast',month=today[:7],label='Base',incoming_cents=50000,outgoing_cents=30000)
    assert controls(pid)['forecasts'][0]['incoming_cents']==50000
    denied('legal.finance.forecast.save',project_id=pid,request_id='invalid-month',month='2026-13',label='Base',incoming_cents=0,outgoing_cents=0)


def test_mileage_creates_one_unapproved_expense_and_is_profile_isolated(tmp_path):
    pid,mid=seed(tmp_path)
    p=dict(project_id=pid,request_id='km',matter_id=mid,activity_date=date.today().isoformat(),responsible_user='alice',route='Cabinet - tribunal',distance_milli=12500,rate_cents=60,rate_source='Convention interne 2026')
    call('legal.finance.mileage.add',**p);call('legal.finance.mileage.add',**p)
    rows=controls(pid)['mileage'];assert len(rows)==1 and rows[0]['amount_cents']==750
    fee=next(f for f in call('legal.snapshot',project_id=pid)['fees'] if f['id']==rows[0]['fee_id'])
    assert fee['cost_cents']==750 and fee['approval_status']=='draft' and not fee['billable']
    home=tmp_path/'other';home.mkdir()
    token=set_hermes_home_override(home)
    try:
        denied('legal.finance.snapshot',project_id=pid)
        other,_=seed(home)
        assert not controls(other)['mileage']
    finally: reset_hermes_home_override(token)
    assert controls(pid)['mileage'][0]['amount_cents']==750


def test_reminder_levels_follow_real_unpaid_balance_and_stop_when_settled(tmp_path,monkeypatch):
    pid,mid=seed(tmp_path)
    fees=call('legal.fee.add',project_id=pid,request_id='fee',matter_id=mid,kind='fixed',description='Honoraires',amount_cents=10000,cost_cents=0)['fees']
    invoice=call('legal.document.create',project_id=pid,request_id='invoice',matter_id=mid,kind='invoice',fee_ids=[fees[0]['id']],due_on=date.today().isoformat())['documents'][0]
    from hermes_cli import legal_finance
    class Later(date):
        @classmethod
        def today(cls): return date.today()+timedelta(days=5)
    monkeypatch.setattr(legal_finance,'date',Later)
    p=dict(project_id=pid,request_id='level-one',document_id=invoice['id'],level=1,message='Merci de vérifier votre règlement.')
    call('legal.finance.reminder.prepare',**p);call('legal.finance.reminder.prepare',**p)
    denied('legal.finance.reminder.prepare',**{**p,'request_id':'skip','level':3})
    call('legal.payment.add',project_id=pid,request_id='partial',document_id=invoice['id'],amount_cents=2000,paid_on=date.today().isoformat(),reference='Saisie partielle')
    call('legal.finance.reminder.prepare',**{**p,'request_id':'two','level':2})
    drafts=controls(pid)['reminders']
    assert next(r for r in drafts if r['level']==2)['balance_cents']==8000
    assert all(r['status']=='draft' for r in drafts)
    call('legal.payment.add',project_id=pid,request_id='settled',document_id=invoice['id'],amount_cents=8000,paid_on=date.today().isoformat(),reference='Solde saisi')
    denied('legal.finance.reminder.prepare',**{**p,'request_id':'settled-reminder','level':3})
