"""Cabinet CRM, procurement and service contracts over the profile-owned ledger.

Original Actelyo implementation. These records do not send purchase orders or payments.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_business_parties(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, role TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
 address TEXT NOT NULL, notes TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS legal_business_contracts(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 party_id TEXT NOT NULL, title TEXT NOT NULL, start_on TEXT NOT NULL, end_on TEXT NOT NULL,
 amount_cents INTEGER NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS legal_purchase_orders(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 supplier_id TEXT NOT NULL, reference TEXT NOT NULL, due_on TEXT NOT NULL,
 lines TEXT NOT NULL, net_cents INTEGER NOT NULL, tax_cents INTEGER NOT NULL,
 total_cents INTEGER NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
 UNIQUE(project_id,reference));
CREATE TABLE IF NOT EXISTS legal_supplier_payments(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 order_id TEXT NOT NULL, amount_cents INTEGER NOT NULL, paid_on TEXT NOT NULL, reference TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS legal_time_trackers(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL, description TEXT NOT NULL, rate_cents INTEGER NOT NULL,
 cost_rate_cents INTEGER, billable INTEGER NOT NULL, seconds INTEGER NOT NULL,
 running_since TEXT, status TEXT NOT NULL, version INTEGER NOT NULL);
"""

def _now():
    return datetime.now(timezone.utc)


def _row(conn, table, pid, identifier):
    # Table names are selected by the module, never provided by a caller.
    row = conn.execute(f'SELECT * FROM {table} WHERE id=? AND project_id=?', (identifier, pid)).fetchone()
    if row is None:
        raise ValueError('Enregistrement absent de cet espace.')
    return dict(row)


def _version(row, p):
    if (row['version'] if row else 0) != p['expected_version']:
        raise ValueError('Cet enregistrement a changé. Actualisez avant de continuer.')


def _party(conn, pid, p):
    from .legal_practice import _legal_text
    previous = _row(conn, 'legal_business_parties', pid, p['id']) if p.get('id') else None
    _version(previous, p)
    identifier = previous['id'] if previous else secrets.token_hex(16)
    if previous and previous['role'] == 'supplier' and p['role'] != 'supplier':
        if conn.execute('SELECT 1 FROM legal_purchase_orders WHERE supplier_id=? AND project_id=?', (identifier,pid)).fetchone():
            raise ValueError('Un fournisseur lié à un achat doit conserver ce rôle.')
    values = [identifier, pid, _legal_text(p['name'],required=True,limit=200), p['role'],
              _legal_text(p.get('email'),limit=320), _legal_text(p.get('phone'),limit=100),
              _legal_text(p.get('address'),limit=2000), _legal_text(p.get('notes'),limit=4000), p['expected_version']+1]
    conn.execute('INSERT INTO legal_business_parties VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,role=excluded.role,email=excluded.email,phone=excluded.phone,address=excluded.address,notes=excluded.notes,version=excluded.version', values)


def _contract(conn, pid, p):
    from .legal_practice import _legal_date, _legal_text
    _row(conn, 'legal_business_parties', pid, p['party_id'])
    old = _row(conn,'legal_business_contracts',pid,p['id']) if p.get('id') else None
    _version(old,p)
    start, end = _legal_date(p['start_on']), _legal_date(p['end_on'])
    if end < start:
        raise ValueError('La fin du contrat précède son début.')
    conn.execute('INSERT INTO legal_business_contracts VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET party_id=excluded.party_id,title=excluded.title,start_on=excluded.start_on,end_on=excluded.end_on,amount_cents=excluded.amount_cents,status=excluded.status,version=excluded.version',
                 (old['id'] if old else secrets.token_hex(16),pid,p['party_id'],_legal_text(p['title'],required=True),start,end,p['amount_cents'],p['status'],p['expected_version']+1))


def _purchase(conn, pid, p):
    from .legal_practice import _legal_date, _legal_text, _legal_round
    supplier = _row(conn,'legal_business_parties',pid,p['supplier_id'])
    if supplier['role'] != 'supplier':
        raise ValueError('Choisissez un fournisseur.')
    if conn.execute('SELECT 1 FROM legal_purchase_orders WHERE project_id=? AND reference=?',(pid,p['reference'].strip())).fetchone():
        raise ValueError('Cette référence d’achat existe déjà dans cet espace.')
    lines = []
    for line in p['lines']:
        net = _legal_round(Decimal(line['quantity_milli'])*line['unit_cents']/1000)
        tax = _legal_round(Decimal(net)*line['tax_bps']/10000)
        lines.append({**line,'description':_legal_text(line['description'],required=True),'net_cents':net,'tax_cents':tax})
    net, tax = sum(line['net_cents'] for line in lines), sum(line['tax_cents'] for line in lines)
    if net+tax > 1_000_000_000:
        raise ValueError('Montant total d’achat trop élevé.')
    conn.execute('INSERT INTO legal_purchase_orders VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['supplier_id'],_legal_text(p['reference'],required=True,limit=100),_legal_date(p['due_on']),json.dumps(lines,ensure_ascii=False),net,tax,net+tax,'draft',1))


def _transition(conn, pid, p):
    order = _row(conn,'legal_purchase_orders',pid,p['order_id'])
    _version(order,p)
    allowed = {'draft':{'ordered','cancelled'},'ordered':{'received','cancelled'},'received':{'closed'},'closed':set(),'cancelled':set()}
    if p['status'] not in allowed[order['status']]:
        raise ValueError('Transition d’achat non autorisée.')
    paid = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM legal_supplier_payments WHERE project_id=? AND order_id=?',(pid,order['id'])).fetchone()[0]
    if p['status']=='closed' and paid != order['total_cents']:
        raise ValueError('Le montant réglé doit correspondre au total pour clôturer.')
    conn.execute('UPDATE legal_purchase_orders SET status=?,version=version+1 WHERE id=? AND project_id=?',(p['status'],order['id'],pid))


def _payment(conn, pid, p):
    from .legal_practice import _legal_date, _legal_text
    order = _row(conn,'legal_purchase_orders',pid,p['order_id'])
    if order['status'] != 'received':
        raise ValueError('Réceptionnez l’achat avant de saisir son règlement.')
    paid = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM legal_supplier_payments WHERE project_id=? AND order_id=?',(pid,order['id'])).fetchone()[0]
    if p['amount_cents'] > order['total_cents']-paid:
        raise ValueError('Le règlement dépasse le solde fournisseur.')
    paid_on = _legal_date(p['paid_on'])
    if paid_on > date.today().isoformat():
        raise ValueError('Un règlement réalisé ne peut pas être daté dans le futur.')
    conn.execute('INSERT INTO legal_supplier_payments VALUES(?,?,?,?,?,?)',(secrets.token_hex(16),pid,order['id'],p['amount_cents'],paid_on,_legal_text(p['reference'],required=True)))


def _timer_start(conn, pid, p):
    from .legal_practice import _legal_row, _legal_text
    _legal_row(conn,'legal_matters',pid,p['matter_id'])
    responsible=_legal_text(p.get('responsible_user'),limit=200)
    if conn.execute("SELECT 1 FROM legal_time_trackers WHERE project_id=? AND responsible_user=? AND status='running'",(pid,responsible)).fetchone():
        raise ValueError('Suspendez le minuteur actif avant d’en démarrer un autre.')
    conn.execute('INSERT INTO legal_time_trackers(id,project_id,matter_id,description,rate_cents,cost_rate_cents,billable,seconds,running_since,status,version,responsible_user) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['matter_id'],_legal_text(p['description'],required=True),p['rate_cents'],p.get('cost_rate_cents'),int(p['billable']),0,_now().isoformat(),'running',1,responsible))


def _timer_change(conn, pid, p):
    timer = _row(conn,'legal_time_trackers',pid,p['timer_id'])
    _version(timer,p)
    command = p['command']
    if command=='pause' and timer['status']=='running':
        seconds = timer['seconds']+max(0,int((_now()-datetime.fromisoformat(timer['running_since'])).total_seconds()))
        conn.execute("UPDATE legal_time_trackers SET seconds=?,running_since=NULL,status='paused',version=version+1 WHERE id=? AND project_id=?",(seconds,timer['id'],pid))
        return
    if command=='resume' and timer['status']=='paused':
        if conn.execute("SELECT 1 FROM legal_time_trackers WHERE project_id=? AND responsible_user=? AND status='running'",(pid,timer['responsible_user'])).fetchone():
            raise ValueError('Un autre minuteur est actif.')
        conn.execute("UPDATE legal_time_trackers SET running_since=?,status='running',version=version+1 WHERE id=? AND project_id=?",(_now().isoformat(),timer['id'],pid))
        return
    if command=='finish' and timer['status']=='paused' and timer['seconds']>0:
        from .legal_practice import _legal_apply
        _legal_apply(conn,pid,'fee.add',{'matter_id':timer['matter_id'],'description':timer['description'],'kind':'time','minutes':(timer['seconds']+59)//60,'rate_cents':timer['rate_cents'],'cost_rate_cents':timer['cost_rate_cents'],'billable':bool(timer['billable']),'responsible_user':timer['responsible_user'],'approval_status':'draft'})
        conn.execute("UPDATE legal_time_trackers SET status='finished',version=version+1 WHERE id=? AND project_id=?",(timer['id'],pid))
        return
    raise ValueError('Transition de minuteur invalide. Suspendez-le avant de créer la diligence.')


HANDLERS = {'business.party.save':_party,'business.contract.save':_contract,'business.purchase.save':_purchase,
            'business.purchase.transition':_transition,'business.supplier_payment.add':_payment,
            'finance.timer.start':_timer_start,'finance.timer.change':_timer_change}


from . import legal_finance_control, legal_billing_orders, legal_finance_files
SCHEMA += legal_finance_control.SCHEMA + legal_billing_orders.SCHEMA + legal_finance_files.SCHEMA
HANDLERS.update(legal_finance_control.HANDLERS)
HANDLERS.update(legal_billing_orders.HANDLERS)
HANDLERS.update(legal_finance_files.HANDLERS)


def apply(conn, pid, action, p):
    return HANDLERS[action](conn,pid,p)


def snapshot(conn, pid):
    parties = [dict(r) for r in conn.execute('SELECT * FROM legal_business_parties WHERE project_id=? ORDER BY name,id',(pid,))]
    contracts = [dict(r) for r in conn.execute('SELECT * FROM legal_business_contracts WHERE project_id=? ORDER BY end_on,id',(pid,))]
    payments = [dict(r) for r in conn.execute('SELECT * FROM legal_supplier_payments WHERE project_id=? ORDER BY paid_on,id',(pid,))]
    purchases = [dict(r) for r in conn.execute('SELECT * FROM legal_purchase_orders WHERE project_id=? ORDER BY reference,id',(pid,))]
    for order in purchases:
        order['lines'] = json.loads(order['lines'])
        order['paid_cents'] = sum(p['amount_cents'] for p in payments if p['order_id']==order['id'])
        order['balance_cents'] = order['total_cents']-order['paid_cents'] if order['status']!='cancelled' else 0
    timers = [dict(r) for r in conn.execute('SELECT * FROM legal_time_trackers WHERE project_id=? ORDER BY id',(pid,))]
    for timer in timers:
        timer['elapsed_seconds'] = timer['seconds']+(max(0,int((_now()-datetime.fromisoformat(timer['running_since'])).total_seconds())) if timer['running_since'] else 0)
    return {'files':legal_finance_files.snapshot(conn,pid),'billing_orders':legal_billing_orders.snapshot(conn,pid),'controls':legal_finance_control.snapshot(conn,pid),'parties':parties,'contracts':contracts,'purchases':purchases,'supplier_payments':payments,'timers':timers,
            'supplier_balance_cents':sum(p['balance_cents'] for p in purchases if p['status'] in ('received','closed')),
            'scope':'Registre interne : aucun bon de commande envoyé, paiement bancaire ou signature de contrat effectué.'}
