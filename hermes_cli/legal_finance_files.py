"""Profile/project-owned financial documents, bounded chunk transfer and derived PDF copies."""
import base64
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

MAX_BYTES=5_000_000
CHUNK_BYTES=36_000
META_COLUMNS='id,project_id,matter_id,filename,kind,size_bytes,sha256,created_on,source_file_id,piece_number,extraction_mode,extraction_source_id'
SCHEMA="""
CREATE TABLE IF NOT EXISTS legal_finance_uploads(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL, filename TEXT NOT NULL, kind TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, created_on TEXT NOT NULL,
 file_id TEXT, request_id TEXT NOT NULL, UNIQUE(project_id,request_id));
CREATE TABLE IF NOT EXISTS legal_finance_chunks(
 upload_id TEXT NOT NULL REFERENCES legal_finance_uploads(id) ON DELETE CASCADE,
 sequence INTEGER NOT NULL, data BLOB NOT NULL, PRIMARY KEY(upload_id,sequence));
CREATE TABLE IF NOT EXISTS legal_finance_files(
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL, filename TEXT NOT NULL, kind TEXT NOT NULL,
 size_bytes INTEGER NOT NULL, sha256 TEXT NOT NULL, created_on TEXT NOT NULL,
 data BLOB NOT NULL, source_file_id TEXT, piece_number INTEGER NOT NULL DEFAULT 0,
 extracted_text TEXT NOT NULL DEFAULT '', extraction_mode TEXT NOT NULL DEFAULT 'not_requested');
CREATE UNIQUE INDEX IF NOT EXISTS legal_finance_piece_number ON legal_finance_files(project_id,matter_id,piece_number) WHERE piece_number>0;
"""


def migrate(conn):
    if 'extraction_source_id' not in {r['name'] for r in conn.execute('PRAGMA table_info(legal_finance_files)')}:
        conn.execute('ALTER TABLE legal_finance_files ADD COLUMN extraction_source_id TEXT')


def _row(conn,table,pid,identifier):
    from .legal_practice import _legal_row
    return _legal_row(conn,table,pid,identifier)


def _meta(row):
    return {k:row[k] for k in META_COLUMNS.split(',')}


def snapshot(conn,pid):
    return [dict(r) for r in conn.execute(f'SELECT {META_COLUMNS} FROM legal_finance_files WHERE project_id=? ORDER BY created_on,id',(pid,))]


def _start(conn,pid,p):
    _row(conn,'legal_matters',pid,p['matter_id'])
    if not re.fullmatch(r'[a-f0-9]{64}',p['sha256']): raise ValueError('Empreinte SHA-256 invalide.')
    name=p['filename'].strip()
    ocr=p['kind']=='ocr_result'
    valid_name=bool(re.fullmatch(r'ocr-[a-f0-9]{32}\.json',name)) if ocr else name.lower().endswith('.pdf')
    if not valid_name or any(ord(c)<32 or c in '/\\' for c in name):
        raise ValueError('Nom de document simple et type de fichier cohérent requis.')
    old=conn.execute('SELECT * FROM legal_finance_uploads WHERE project_id=? AND request_id=?',(pid,p['request_id'])).fetchone()
    if old:
        if old['filename']!=name or any(old[k]!=p[k] for k in ('matter_id','kind','size_bytes','sha256')): raise ValueError('Requête de dépôt réutilisée avec un autre contenu.')
        return {'upload_id':old['id'],'chunk_bytes':CHUNK_BYTES}
    if conn.execute('SELECT COUNT(*) FROM legal_finance_uploads WHERE project_id=? AND file_id IS NULL',(pid,)).fetchone()[0]>=5:
        raise ValueError('Terminez ou annulez les dépôts en cours avant de continuer.')
    identifier=secrets.token_hex(16)
    conn.execute('INSERT INTO legal_finance_uploads VALUES(?,?,?,?,?,?,?,?,?,?)',
                 (identifier,pid,p['matter_id'],name,p['kind'],p['size_bytes'],p['sha256'],datetime.now(timezone.utc).isoformat(),None,p['request_id']))
    return {'upload_id':identifier,'chunk_bytes':CHUNK_BYTES}


def _chunk(conn,pid,p):
    upload=_row(conn,'legal_finance_uploads',pid,p['upload_id'])
    if upload['file_id']: raise ValueError('Ce dépôt est déjà terminé.')
    try: data=base64.b64decode(p['data_base64'],validate=True)
    except (ValueError,TypeError): raise ValueError('Bloc encodé invalide.') from None
    offset=p['sequence']*CHUNK_BYTES
    expected=min(CHUNK_BYTES,upload['size_bytes']-offset)
    if expected<=0 or len(data)!=expected: raise ValueError('Taille ou position du bloc invalide.')
    old=conn.execute('SELECT data FROM legal_finance_chunks WHERE upload_id=? AND sequence=?',(upload['id'],p['sequence'])).fetchone()
    if old and bytes(old['data'])!=data: raise ValueError('Un bloc déjà reçu ne peut pas être remplacé.')
    conn.execute('INSERT OR IGNORE INTO legal_finance_chunks VALUES(?,?,?)',(upload['id'],p['sequence'],data))
    return {'upload_id':upload['id'],'sequence':p['sequence'],'accepted_bytes':len(data)}


def _finish(conn,pid,p):
    upload=_row(conn,'legal_finance_uploads',pid,p['upload_id'])
    if upload['file_id']: return _meta(_row(conn,'legal_finance_files',pid,upload['file_id']))
    chunks=conn.execute('SELECT sequence,data FROM legal_finance_chunks WHERE upload_id=? ORDER BY sequence',(upload['id'],)).fetchall()
    if [r['sequence'] for r in chunks]!=list(range((upload['size_bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)):
        raise ValueError('Le fichier est incomplet. Reprendre les blocs manquants.')
    data=b''.join(bytes(r['data']) for r in chunks)
    if len(data)!=upload['size_bytes'] or hashlib.sha256(data).hexdigest()!=upload['sha256']:
        raise ValueError('Le contrôle d’intégrité du fichier a échoué.')
    source=None;ocr_text=None;ocr_mode=None
    if upload['kind']=='ocr_result':
        from .legal_finance_ocr import validate
        source,ocr_text,ocr_mode=validate(conn,pid,upload,data)
    else:
        if not data.startswith(b'%PDF-'): raise ValueError('Le fichier ne contient pas un PDF.')
        _worker({'data':data},'inspect')
    source_id=source['id'] if source else None
    existing=conn.execute('SELECT id FROM legal_finance_files WHERE project_id=? AND matter_id=? AND sha256=? AND kind=? AND source_file_id IS ?',
                          (pid,upload['matter_id'],upload['sha256'],upload['kind'],source_id)).fetchone()
    identifier=existing['id'] if existing else secrets.token_hex(16)
    if not existing:
        conn.execute('INSERT INTO legal_finance_files(id,project_id,matter_id,filename,kind,size_bytes,sha256,created_on,data,source_file_id,piece_number,extracted_text,extraction_mode) VALUES(?,?,?,?,?,?,?,?,?,?,0,?,?)',
                     (identifier,pid,upload['matter_id'],upload['filename'],upload['kind'],len(data),upload['sha256'],datetime.now(timezone.utc).isoformat(),data,source_id,'','not_requested'))
    if source:
        conn.execute("UPDATE legal_finance_files SET extracted_text=?,extraction_mode=?,extraction_source_id=? WHERE id=? AND project_id=?",(ocr_text,ocr_mode,identifier,source['id'],pid))
    conn.execute('UPDATE legal_finance_uploads SET file_id=? WHERE id=? AND project_id=?',(identifier,upload['id'],pid))
    conn.execute('DELETE FROM legal_finance_chunks WHERE upload_id=?',(upload['id'],))
    return _meta(_row(conn,'legal_finance_files',pid,identifier))


def _cancel(conn,pid,p):
    upload=_row(conn,'legal_finance_uploads',pid,p['upload_id'])
    if upload['file_id']: raise ValueError('Le document est déposé ; l’annulation du transfert ne le supprime pas.')
    conn.execute('DELETE FROM legal_finance_chunks WHERE upload_id=?',(upload['id'],))
    conn.execute('DELETE FROM legal_finance_uploads WHERE id=? AND project_id=?',(upload['id'],pid))
    return {'upload_id':upload['id'],'cancelled':True}


def _read(conn,pid,p):
    row=conn.execute('SELECT id,size_bytes,sha256,filename FROM legal_finance_files WHERE id=? AND project_id=?',(p['file_id'],pid)).fetchone()
    if not row: raise ValueError('Document absent de cet espace.')
    if p['offset']>row['size_bytes']: raise ValueError('Position de téléchargement invalide.')
    data=bytes(conn.execute('SELECT substr(data,?,?) FROM legal_finance_files WHERE id=? AND project_id=?',(p['offset']+1,CHUNK_BYTES,p['file_id'],pid)).fetchone()[0])
    return {'file_id':row['id'],'offset':p['offset'],'data_base64':base64.b64encode(data).decode(),
            'size_bytes':row['size_bytes'],'sha256':row['sha256'],'filename':row['filename']}


def _text(conn,pid,p):
    row=_row(conn,'legal_finance_files',pid,p['file_id'])
    return {'file_id':row['id'],'sha256':row['sha256'],'text':row['extracted_text'],'mode':row['extraction_mode'],'extraction_source_id':row['extraction_source_id'],'untrusted':True}


def tool_text(conn,pid,values):
    from .legal_practice import _legal_integer
    values=dict(values);payload=values.pop('operation_payload',{})
    if not isinstance(payload,dict) or set(payload)-{'file_id'} or set(values)-{'file_id','document_offset'}:
        raise ValueError('Lecture documentaire : seuls file_id et document_offset sont autorisés.')
    identifier=payload.get('file_id') or values.get('file_id')
    offset=_legal_integer(values.get('document_offset',0),high=150000)
    result=_text(conn,pid,{'file_id':identifier})
    text=result['text'];end=min(len(text),offset+12000)
    if offset>len(text): raise ValueError('Position hors du texte extrait.')
    result.update(text=text[offset:end],document_offset=offset,total_characters=len(text),truncated=end<len(text),next_offset=end if end<len(text) else None)
    return result


TRANSFERS={'finance.file.start':_start,'finance.file.chunk':_chunk,'finance.file.finish':_finish,
           'finance.file.cancel':_cancel,'finance.file.read':_read,'finance.file.text':_text}


def transfer(conn,pid,action,p):
    from .legal_practice import write_txn
    with write_txn(conn): return TRANSFERS[action](conn,pid,p)


def _worker(row,operation,**params):
    from tools.environments.local import served_profile_child_env
    # A bundled launcher adds its dependencies in-process. A new bare Python
    # process does not inherit sys.path; select that same package directory
    # explicitly, without inheriting PYTHONPATH or executing third-party .pth.
    pdf=importlib.util.find_spec('pypdf')
    if pdf is None or not pdf.origin or not pdf.submodule_search_locations:
        raise ValueError('Module PDF local absent : installer les dépendances finance du Law Harness.')
    dependencies=str(Path(pdf.origin).resolve().parent.parent)
    bootstrap=('import runpy,sys; worker,dependencies=sys.argv[1:]; '
               'sys.path.append(dependencies); sys.argv=[worker]; '
               'runpy.run_path(worker,run_name="__main__")')
    request={'operation':operation,'data_base64':base64.b64encode(row['data']).decode(),**params}
    try:
        process=subprocess.run([sys.executable,'-I','-S','-X','utf8','-c',bootstrap,str(Path(__file__).with_name('legal_pdf_worker.py')),dependencies],
             input=json.dumps(request).encode(),capture_output=True,timeout=30,env=served_profile_child_env(),
             creationflags=0x08000000 if sys.platform=='win32' else 0)
    except subprocess.TimeoutExpired: raise ValueError('Délai PDF dépassé ; original conservé.') from None
    try: reply=json.loads(process.stdout.decode())
    except (ValueError,UnicodeDecodeError): raise ValueError('Traitement PDF interrompu ; original conservé.') from None
    if not reply.get('ok'): raise ValueError(reply.get('error','Traitement PDF refusé.'))
    return reply['result']


def _extract(conn,pid,p):
    row=_row(conn,'legal_finance_files',pid,p['file_id'])
    result=_worker(row,'extract')
    conn.execute('UPDATE legal_finance_files SET extracted_text=?,extraction_mode=?,extraction_source_id=NULL WHERE id=? AND project_id=?',
                 (result['text'],result['mode'],row['id'],pid))


def _stamp(conn,pid,p):
    row=_row(conn,'legal_finance_files',pid,p['file_id'])
    if row['source_file_id']: raise ValueError('Tamponnez le document original, pas une copie déjà tamponnée.')
    if conn.execute('SELECT 1 FROM legal_finance_files WHERE project_id=? AND matter_id=? AND piece_number=?',(pid,row['matter_id'],p['piece_number'])).fetchone():
        raise ValueError('Ce numéro de pièce est déjà utilisé dans ce dossier.')
    result=_worker(row,'stamp',piece_number=p['piece_number'])
    data=base64.b64decode(result['data_base64'],validate=True)
    conn.execute('INSERT INTO legal_finance_files(id,project_id,matter_id,filename,kind,size_bytes,sha256,created_on,data,source_file_id,piece_number,extracted_text,extraction_mode) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                 (secrets.token_hex(16),pid,row['matter_id'],f"piece-{p['piece_number']:03d}-"+row['filename'],'evidence',len(data),hashlib.sha256(data).hexdigest(),
                  datetime.now(timezone.utc).isoformat(),data,row['id'],p['piece_number'],'','not_requested'))


HANDLERS={'finance.file.extract':_extract,'finance.file.stamp':_stamp}
