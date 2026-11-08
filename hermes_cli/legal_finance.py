"""Project-owned budgets, reviewed production and cash ageing over the native ledger.

All amounts are integer cents. No invoice issuance, external collection or tax inference.
"""
from datetime import date
import csv
import io

SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_finance_budgets (
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id) ON DELETE CASCADE,
 budget_minutes INTEGER NOT NULL, revenue_cents INTEGER NOT NULL,
 cost_cents INTEGER NOT NULL, version INTEGER NOT NULL,
 PRIMARY KEY(project_id,matter_id)
);
CREATE TABLE IF NOT EXISTS legal_fee_reviews (
 id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, fee_id TEXT NOT NULL,
 previous_status TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
 reviewed_on TEXT NOT NULL
);
"""


def apply(conn, pid, action, p):
    from hermes_cli.legal_practice import _legal_integer, _legal_row, _legal_text
    if action == 'finance.budget.save':
        _legal_row(conn, 'legal_matters', pid, p.get('matter_id'))
        current = conn.execute('SELECT version FROM legal_finance_budgets WHERE project_id=? AND matter_id=?', (pid,p['matter_id'])).fetchone()
        version = current['version'] if current else 0
        if _legal_integer(p.get('expected_version'), high=1_000_000) != version:
            raise ValueError('Le budget a changé. Actualisez avant de le modifier.')
        minutes = _legal_integer(p.get('budget_minutes',0), high=1_000_000)
        revenue = _legal_integer(p.get('revenue_cents',0))
        cost = _legal_integer(p.get('cost_cents',0))
        conn.execute('INSERT INTO legal_finance_budgets VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,matter_id) DO UPDATE SET budget_minutes=excluded.budget_minutes,revenue_cents=excluded.revenue_cents,cost_cents=excluded.cost_cents,version=excluded.version', (pid,p['matter_id'],minutes,revenue,cost,version+1))
        return
    if action == 'finance.fee.review':
        fee = _legal_row(conn,'legal_fees',pid,p.get('fee_id'))
        if fee['invoice_id']:
            raise ValueError('Une diligence facturée ne peut plus changer de validation.')
        status = p.get('approval_status')
        if status not in ('draft','approved','rejected'):
            raise ValueError('État de validation invalide.')
        reason = _legal_text(p.get('reason'), required=True, limit=2000)
        conn.execute('UPDATE legal_fees SET approval_status=? WHERE id=? AND project_id=?',(status,fee['id'],pid))
        conn.execute('INSERT INTO legal_fee_reviews(project_id,fee_id,previous_status,status,reason,reviewed_on) VALUES(?,?,?,?,?,?)',(pid,fee['id'],fee['approval_status'],status,reason,date.today().isoformat()))
        return
    raise ValueError('Opération de pilotage inconnue.')


def snapshot(conn, pid):
    return _snapshot(conn,pid)


def _snapshot(conn, pid):
    if conn.execute('SELECT id FROM projects WHERE id=?',(pid,)).fetchone() is None:
        raise ValueError('Projet introuvable.')
    today = date.today()
    matters = [dict(r) for r in conn.execute('SELECT m.id,m.title,m.reference,c.name AS client FROM legal_matters m JOIN legal_clients c ON c.id=m.client_id AND c.project_id=m.project_id WHERE m.project_id=? ORDER BY m.title,m.id',(pid,))]
    fees = [dict(r) for r in conn.execute('SELECT * FROM legal_fees WHERE project_id=?',(pid,))]
    documents = [dict(r) for r in conn.execute('SELECT * FROM legal_documents WHERE project_id=?',(pid,))]
    payments = [dict(r) for r in conn.execute('SELECT * FROM legal_payments WHERE project_id=?',(pid,))]
    budgets = {r['matter_id']:dict(r) for r in conn.execute('SELECT * FROM legal_finance_budgets WHERE project_id=?',(pid,))}
    ageing = {'not_due':0,'days_1_30':0,'days_31_60':0,'days_61_90':0,'days_over_90':0}
    receivables = []
    for document in documents:
        if document['kind'] != 'invoice': continue
        paid = sum(p['amount_cents'] for p in payments if p['document_id']==document['id'])
        credited = sum(d['total_cents'] for d in documents if d.get('related_document_id')==document['id'] and d['kind']=='credit_note')
        balance = max(0,document['total_cents']-paid-credited)
        if not balance: continue
        overdue = max(0,(today-date.fromisoformat(document['due_on'])).days)
        bucket = 'not_due' if not overdue else 'days_1_30' if overdue<=30 else 'days_31_60' if overdue<=60 else 'days_61_90' if overdue<=90 else 'days_over_90'
        ageing[bucket] += balance
        matter = next(m for m in matters if m['id']==document['matter_id'])
        receivables.append({'document_id':document['id'],'matter_id':matter['id'],'client':matter['client'],'reference':document['reference'],'due_on':document['due_on'],'overdue_days':overdue,'balance_cents':balance,'bucket':bucket})
    for matter in matters:
        own = [f for f in fees if f['matter_id']==matter['id']]
        active = [f for f in own if f['approval_status']!='rejected']
        missing_costs = sum(f['cost_cents'] is None for f in active)
        budget = budgets.get(matter['id'])
        cost = sum(f['cost_cents'] or 0 for f in active)
        billed = sum(d['net_cents']*(1 if d['kind']=='invoice' else -1 if d['kind']=='credit_note' else 0) for d in documents if d['matter_id']==matter['id'])
        matter.update({'minutes':sum(f['minutes'] for f in active if f['kind']=='time'),
            'billable_minutes':sum(f['minutes'] for f in active if f['kind']=='time' and f['billable']),
            'unbilled_cents':sum(f['net_cents'] for f in active if f['billable'] and not f['invoice_id'] and f['approval_status']=='approved'),
            'pending_cents':sum(f['net_cents'] for f in active if f['billable'] and f['approval_status']=='draft'),
            'cost_cents':cost,'missing_costs':missing_costs,'billed_net_cents':billed,
            'margin_cents':billed-cost if not missing_costs else None,
            'cash_received_cents':sum(p['amount_cents'] for p in payments if any(d['id']==p['document_id'] and d['matter_id']==matter['id'] for d in documents)),
            'outstanding_cents':sum(r['balance_cents'] for r in receivables if r['matter_id']==matter['id']),
            'budget':{k:budget[k] for k in ('budget_minutes','revenue_cents','cost_cents','version')} if budget else None})
        matter['time_over_budget'] = bool(budget and budget['budget_minutes'] and matter['minutes']>budget['budget_minutes'])
        matter['cost_over_budget'] = bool(budget and budget['cost_cents'] and cost>budget['cost_cents'])
    totals = {key:sum(m[key] for m in matters) for key in ('minutes','billable_minutes','unbilled_cents','pending_cents','cost_cents','billed_net_cents','cash_received_cents','outstanding_cents','missing_costs')}
    totals['margin_cents'] = totals['billed_net_cents']-totals['cost_cents'] if not totals['missing_costs'] else None
    from hermes_cli.legal_operations import snapshot as operations_snapshot
    return {'project_id':pid,'as_of':today.isoformat(),'currency':'EUR','totals':totals,'matters':matters,'ageing':ageing,'receivables':receivables,'operations':operations_snapshot(conn,pid),
            'pending_fees':[{'id':f['id'],'matter_id':f['matter_id'],'description':f['description'],'net_cents':f['net_cents'],'activity_date':f['activity_date'],'expense_type':f['expense_type'],'approval_status':f['approval_status']} for f in fees if f['approval_status']=='draft' and not f['invoice_id']],
            'ready_fees':[{'id':f['id'],'matter_id':f['matter_id'],'description':f['description'],'net_cents':f['net_cents'],'activity_date':f['activity_date'],'expense_type':f['expense_type'],'approval_status':f['approval_status']} for f in fees if f['approval_status']=='approved' and f['billable'] and not f['invoice_id']],
            'scope':'Pilotage du registre local : les factures sont des documents internes et les règlements sont saisis, sans vérification bancaire. Les encours et marges incluent ces factures internes, sans preuve d’émission. HT pour production/marge, TTC pour encours/règlements. Coûts manquants : marge non calculée. Aucune émission fiscale ni transmission effectuée.'}


def export_csv(conn, pid):
    data = _snapshot(conn,pid)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream,delimiter=';',lineterminator='\r\n')
    writer.writerow(['Dossier','Client','Minutes','Non facture HT centimes','A valider HT centimes','Factures internes HT centimes','Cout saisi centimes','Marge projetee HT centimes','Encours TTC centimes','Couts manquants'])
    def cell(value):
        if type(value) is int:return str(value)
        text = str(value if value is not None else '')
        return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
    for m in data['matters']:
        writer.writerow([cell(m[key]) for key in ('title','client','minutes','unbilled_cents','pending_cents','billed_net_cents','cost_cents','margin_cents','outstanding_cents','missing_costs')])
    return {'filename':'actelyo-pilotage-'+data['as_of']+'.csv','content':'\ufeff'+stream.getvalue(),'mime':'text/csv;charset=utf-8','scope':'Export de pilotage, pas un FEC ni une facture électronique.'}
