"""Immutable, numbered billing approvals over the existing native fee ledger."""
from datetime import date
import hashlib
import json
import secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_billing_orders(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL, reference TEXT NOT NULL, created_on TEXT NOT NULL,
 purpose TEXT NOT NULL, fee_ids TEXT NOT NULL, source_digest TEXT NOT NULL,
 lines TEXT NOT NULL, net_cents INTEGER NOT NULL, tax_cents INTEGER NOT NULL,
 total_cents INTEGER NOT NULL, status TEXT NOT NULL, document_id TEXT,
 version INTEGER NOT NULL, UNIQUE(project_id,reference));
"""


def _fees(conn,pid,mid,ids,purpose):
    from .legal_practice import _legal_row
    _legal_row(conn,'legal_matters',pid,mid)
    if not ids or len(ids)>500 or len(ids)!=len(set(ids)):
        raise ValueError('Sélectionnez entre 1 et 500 lignes distinctes.')
    fees=[_legal_row(conn,'legal_fees',pid,i) for i in sorted(ids)]
    if any(f['matter_id']!=mid or f['invoice_id'] or not f['billable'] or f['approval_status']!='approved' for f in fees):
        raise ValueError('Le bon exige des lignes du dossier approuvées, facturables et non facturées.')
    if purpose=='provision_fees' and any(f['kind']=='expense' for f in fees):
        raise ValueError('Une provision sur honoraires ne peut inclure de frais.')
    if purpose=='provision_expenses' and any(f['kind']!='expense' for f in fees):
        raise ValueError('Une provision sur frais exige uniquement des frais.')
    return [{k:f[k] for k in ('id','description','kind','minutes','rate_cents','net_cents','tax_bps','tax_cents','responsible_user','activity_date')} for f in fees]


def _digest(lines):
    return hashlib.sha256(json.dumps(lines,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def check_reservations(conn,pid,ids,*,billing_order_id=None):
    for order in conn.execute("SELECT id,fee_ids FROM legal_billing_orders WHERE project_id=? AND status='ready'",(pid,)):
        if set(ids).intersection(json.loads(order['fee_ids'])) and order['id']!=billing_order_id:
            raise ValueError('Des lignes sont réservées par un bon à facturer. Utilisez ce bon ou annulez-le.')


def _create(conn,pid,p):
    lines=_fees(conn,pid,p['matter_id'],p['fee_ids'],p['purpose'])
    chosen=set(p['fee_ids'])
    for existing in conn.execute("SELECT fee_ids FROM legal_billing_orders WHERE project_id=? AND status='ready'",(pid,)):
        if chosen.intersection(json.loads(existing['fee_ids'])):
            raise ValueError('Une ligne est déjà réservée par un bon à facturer actif.')
    number=conn.execute('SELECT COUNT(*) FROM legal_billing_orders WHERE project_id=?',(pid,)).fetchone()[0]+1
    net=sum(f['net_cents'] for f in lines);tax=sum(f['tax_cents'] for f in lines)
    conn.execute('INSERT INTO legal_billing_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['matter_id'],f'BAF-{date.today().year}-{number:05d}',date.today().isoformat(),
                  p['purpose'],json.dumps(sorted(p['fee_ids'])),_digest(lines),json.dumps(lines,ensure_ascii=False),
                  net,tax,net+tax,'ready',None,1))


def _load(conn,pid,p):
    from .legal_practice import _legal_row
    row=_legal_row(conn,'legal_billing_orders',pid,p['billing_order_id'])
    if row['version']!=p['expected_version'] or row['status']!='ready':
        raise ValueError('Ce bon a changé ou n’est plus disponible. Actualisez.')
    return row


def _invoice(conn,pid,p):
    from .legal_practice import _legal_apply
    row=_load(conn,pid,p)
    ids=json.loads(row['fee_ids'])
    if _digest(_fees(conn,pid,row['matter_id'],ids,row['purpose']))!=row['source_digest']:
        raise ValueError('Les lignes ont changé depuis le bon. Annulez-le et préparez un nouveau bon.')
    _legal_apply(conn,pid,'document.create',{'matter_id':row['matter_id'],'kind':'invoice','fee_ids':ids,
                 'purpose':row['purpose'],'due_on':p['due_on'],'template_id':p['template_id']},billing_order_id=row['id'])
    document_id=conn.execute('SELECT invoice_id FROM legal_fees WHERE id=? AND project_id=?',(ids[0],pid)).fetchone()[0]
    if not document_id: raise ValueError('La facture n’a pas été confirmée par le registre.')
    conn.execute("UPDATE legal_billing_orders SET status='invoiced',document_id=?,version=version+1 WHERE id=? AND project_id=?",(document_id,row['id'],pid))


def _cancel(conn,pid,p):
    row=_load(conn,pid,p)
    conn.execute("UPDATE legal_billing_orders SET status='cancelled',version=version+1 WHERE id=? AND project_id=?",(row['id'],pid))


HANDLERS={'finance.billing_order.create':_create,'finance.billing_order.invoice':_invoice,
          'finance.billing_order.cancel':_cancel}


def snapshot(conn,pid):
    rows=[dict(r) for r in conn.execute('SELECT * FROM legal_billing_orders WHERE project_id=? ORDER BY reference DESC',(pid,))]
    for row in rows:
        row['fee_ids']=json.loads(row['fee_ids']);row['lines']=json.loads(row['lines'])
    return rows
