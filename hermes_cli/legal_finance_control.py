"""Sourced accounting imports and cabinet planning. No tax issuance or bank movement."""
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import re
import secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_finance_imports(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 filename TEXT NOT NULL, digest TEXT NOT NULL, imported_on TEXT NOT NULL,
 row_count INTEGER NOT NULL, debit_cents INTEGER NOT NULL, credit_cents INTEGER NOT NULL,
 entries TEXT NOT NULL, UNIQUE(project_id,digest));
CREATE TABLE IF NOT EXISTS legal_finance_objectives(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 responsible_user TEXT NOT NULL, role TEXT NOT NULL, start_on TEXT NOT NULL,end_on TEXT NOT NULL,
 revenue_cents INTEGER NOT NULL, margin_cents INTEGER NOT NULL, minutes INTEGER NOT NULL,
 version INTEGER NOT NULL, UNIQUE(project_id,responsible_user,start_on,end_on));
CREATE TABLE IF NOT EXISTS legal_finance_forecasts(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 month TEXT NOT NULL, label TEXT NOT NULL, incoming_cents INTEGER NOT NULL,
 outgoing_cents INTEGER NOT NULL, version INTEGER NOT NULL, UNIQUE(project_id,month,label));
CREATE TABLE IF NOT EXISTS legal_finance_mileage(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL, activity_date TEXT NOT NULL, responsible_user TEXT NOT NULL,
 route TEXT NOT NULL, distance_milli INTEGER NOT NULL, rate_cents INTEGER NOT NULL,
 rate_source TEXT NOT NULL, amount_cents INTEGER NOT NULL, fee_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS legal_finance_reminders(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 document_id TEXT NOT NULL, level INTEGER NOT NULL, created_on TEXT NOT NULL,
 balance_cents INTEGER NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
 UNIQUE(project_id,document_id,level));
"""

FEC_FIELDS = ('JournalCode','JournalLib','EcritureNum','EcritureDate','CompteNum','CompteLib',
              'CompAuxNum','CompAuxLib','PieceRef','PieceDate','EcritureLib','Debit','Credit',
              'EcritureLet','DateLet','ValidDate','Montantdevise','Idevise')


def _money(value):
    if not re.fullmatch(r'\d+(?:[.,]\d{1,2})?', value.strip()):
        raise ValueError('FEC : montant positif avec deux décimales maximum requis.')
    try:
        amount = int(Decimal(value.strip().replace(',','.'))*100)
    except (InvalidOperation, ValueError):
        raise ValueError('FEC : montant invalide.') from None
    if amount > 1_000_000_000:
        raise ValueError('FEC : montant hors limite.')
    return amount


def parse_fec(content):
    """Supported 18-column debit/credit FEC; this is not a statutory compliance certificate."""
    if '\x00' in content or len(content)>60_000:
        raise ValueError('FEC : texte invalide ou limite de 60 000 caractères dépassée.')
    content=content.lstrip('\ufeff')
    header=content.splitlines()[0] if content.splitlines() else ''
    delimiter='\t' if '\t' in header else '|'
    reader=csv.reader(io.StringIO(content),delimiter=delimiter)
    if tuple(next(reader,())) != FEC_FIELDS:
        raise ValueError('FEC : les 18 colonnes débit/crédit attendues sont requises, dans leur ordre officiel.')
    entries=[]; balances={}; seen=set()
    for line, fields in enumerate(reader,2):
        if not fields: continue
        if len(fields)!=18:
            raise ValueError(f'FEC ligne {line} : 18 champs requis.')
        row=dict(zip(FEC_FIELDS,fields))
        for field in ('JournalCode','EcritureNum','CompteNum','CompteLib','EcritureLib'):
            if not row[field].strip(): raise ValueError(f'FEC ligne {line} : {field} absent.')
        for field in ('EcritureDate','PieceDate','DateLet','ValidDate'):
            if row[field] or field=='EcritureDate':
                try:
                    if not re.fullmatch(r'\d{8}',row[field]): raise ValueError()
                    datetime.strptime(row[field],'%Y%m%d')
                except ValueError:
                    raise ValueError(f'FEC ligne {line} : date {field} invalide.') from None
        if row['Idevise'] not in ('','EUR') or row['Montantdevise']:
            raise ValueError('FEC : les écritures en devise nécessitent un traitement comptable distinct.')
        debit,credit=_money(row['Debit']),_money(row['Credit'])
        if debit and credit: raise ValueError(f'FEC ligne {line} : débit et crédit simultanés.')
        signature=tuple(fields)
        if signature in seen: raise ValueError(f'FEC ligne {line} : ligne identique répétée, rapprochement manuel requis.')
        seen.add(signature)
        key=(row['JournalCode'],row['EcritureNum'])
        balances[key]=balances.get(key,0)+debit-credit
        entries.append({'journal':row['JournalCode'],'number':row['EcritureNum'],
                        'date':datetime.strptime(row['EcritureDate'],'%Y%m%d').date().isoformat(),
                        'account':row['CompteNum'],'reference':row['PieceRef'],'label':row['EcritureLib'],
                        'debit_cents':debit,'credit_cents':credit})
    if not entries: raise ValueError('FEC : aucune écriture.')
    if any(balances.values()): raise ValueError('FEC : au moins une écriture journal/numéro est déséquilibrée.')
    return entries


def _import(conn,pid,p):
    entries=parse_fec(p['content'])
    # Canonical hash makes UTF-8/CP1252 decoding, BOM and newline changes idempotent.
    digest=hashlib.sha256(json.dumps(entries,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if conn.execute('SELECT 1 FROM legal_finance_imports WHERE project_id=? AND digest=?',(pid,digest)).fetchone():
        raise ValueError('Ce contenu comptable est déjà importé dans cet espace.')
    existing=set()
    for old in conn.execute('SELECT entries FROM legal_finance_imports WHERE project_id=?',(pid,)):
        existing.update((e['journal'],e['number'],e['date']) for e in json.loads(old['entries']))
    if any((e['journal'],e['number'],e['date']) in existing for e in entries):
        raise ValueError('Des écritures sont déjà présentes dans un import antérieur. Rapprochement requis.')
    conn.execute('INSERT INTO legal_finance_imports VALUES(?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['filename'],digest,date.today().isoformat(),len(entries),
                  sum(e['debit_cents'] for e in entries),sum(e['credit_cents'] for e in entries),json.dumps(entries,ensure_ascii=False)))


def _save(conn,pid,p,table,fields,key):
    old=conn.execute(f'SELECT * FROM {table} WHERE project_id=? AND '+ ' AND '.join(f'{k}=?' for k in key),
                     (pid,*(p[k] for k in key))).fetchone()
    if (old['version'] if old else 0)!=p['expected_version']:
        raise ValueError('Cette prévision ou cet objectif a changé. Actualisez.')
    identifier=old['id'] if old else secrets.token_hex(16)
    conn.execute(f'INSERT OR REPLACE INTO {table} VALUES('+','.join('?' for _ in range(len(fields)+3))+')',
                 (identifier,pid,*(p[k] for k in fields),p['expected_version']+1))


def _objective(conn,pid,p):
    from .legal_practice import _legal_date
    if _legal_date(p['end_on'])<_legal_date(p['start_on']): raise ValueError('Période d’objectif inversée.')
    if not p['responsible_user'].strip(): raise ValueError('Identifiant du responsable requis.')
    _save(conn,pid,p,'legal_finance_objectives',
          ('responsible_user','role','start_on','end_on','revenue_cents','margin_cents','minutes'),
          ('responsible_user','start_on','end_on'))


def _forecast(conn,pid,p):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',p['month']): raise ValueError('Mois YYYY-MM requis.')
    if not p['label'].strip(): raise ValueError('Libellé de scénario requis.')
    _save(conn,pid,p,'legal_finance_forecasts',('month','label','incoming_cents','outgoing_cents'),('month','label'))


def _mileage(conn,pid,p):
    from .legal_practice import _legal_apply, _legal_date
    from .legal_operations import _row
    _row(conn,'legal_matters',pid,p['matter_id'])
    day=_legal_date(p['activity_date'])
    amount=int((Decimal(p['distance_milli'])*p['rate_cents']/1000).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if not 0<amount<=1_000_000_000: raise ValueError('Indemnité hors limite.')
    before={r[0] for r in conn.execute('SELECT id FROM legal_fees WHERE project_id=?',(pid,))}
    _legal_apply(conn,pid,'fee.add',{'matter_id':p['matter_id'],'kind':'expense','description':'Déplacement : '+p['route'],
                 'activity_date':day,'responsible_user':p['responsible_user'],'amount_cents':amount,'cost_cents':amount,
                 'billable':p['billable'],'expense_type':'office','approval_status':'draft','tax_bps':0})
    fee_id=next(r[0] for r in conn.execute('SELECT id FROM legal_fees WHERE project_id=?',(pid,)) if r[0] not in before)
    conn.execute('INSERT INTO legal_finance_mileage VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['matter_id'],day,p['responsible_user'],p['route'],p['distance_milli'],
                  p['rate_cents'],p['rate_source'],amount,fee_id))


def _reminder(conn,pid,p):
    from .legal_finance import snapshot
    item=next((r for r in snapshot(conn,pid)['receivables'] if r['document_id']==p['document_id']),None)
    if not item or not item['overdue_days']: raise ValueError('Aucune créance échue pour ce document.')
    previous=conn.execute('SELECT MAX(level) FROM legal_finance_reminders WHERE project_id=? AND document_id=?',(pid,p['document_id'])).fetchone()[0] or 0
    if p['level']!=previous+1: raise ValueError('Les niveaux de relance doivent se suivre, sans répétition.')
    label={1:'Rappel amiable',2:'Deuxième relance',3:'Projet de mise en demeure'}[p['level']]
    content=f"{label} — {item['reference']}\nSolde enregistré : {item['balance_cents']/100:.2f} EUR. Échéance : {item['due_on']}.\n{p['message']}"
    conn.execute('INSERT INTO legal_finance_reminders VALUES(?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,p['document_id'],p['level'],date.today().isoformat(),item['balance_cents'],content,'draft'))


HANDLERS={'finance.fec.import':_import,'finance.objective.save':_objective,'finance.forecast.save':_forecast,
          'finance.mileage.add':_mileage,'finance.reminder.prepare':_reminder}


def snapshot(conn,pid):
    rows=lambda table:[dict(r) for r in conn.execute(f'SELECT * FROM {table} WHERE project_id=? ORDER BY id',(pid,))]
    imports=rows('legal_finance_imports')
    invoices={r['reference']:r['id'] for r in conn.execute("SELECT id,reference FROM legal_documents WHERE project_id=? AND kind='invoice'",(pid,))}
    for source in imports:
        entries=json.loads(source.pop('entries'))
        refs=sorted({e['reference'] for e in entries if e['account'].startswith('411') and e['reference']})
        source['matched_references']=[r for r in refs if r in invoices]
        source['unmatched_references']=[r for r in refs if r not in invoices]
        source['revenue_cents']=sum(e['credit_cents']-e['debit_cents'] for e in entries if e['account'].startswith('7'))
        source['expense_cents']=sum(e['debit_cents']-e['credit_cents'] for e in entries if e['account'].startswith('6'))
    objectives=rows('legal_finance_objectives')
    fees=rows('legal_fees')
    for goal in objectives:
        own=[f for f in fees if f['responsible_user']==goal['responsible_user'] and goal['start_on']<=f['activity_date']<=goal['end_on'] and f['approval_status']!='rejected']
        goal['actual_minutes']=sum(f['minutes'] for f in own if f['kind']=='time')
        goal['production_cents']=sum(f['net_cents'] for f in own if f['billable'] and f['approval_status']=='approved')
        goal['missing_costs']=sum(f['cost_cents'] is None for f in own)
        goal['production_margin_cents']=None if goal['missing_costs'] else goal['production_cents']-sum(f['cost_cents'] for f in own)
    return {'imports':imports,'objectives':objectives,'forecasts':rows('legal_finance_forecasts'),
            'mileage':rows('legal_finance_mileage'),'reminders':rows('legal_finance_reminders')}
