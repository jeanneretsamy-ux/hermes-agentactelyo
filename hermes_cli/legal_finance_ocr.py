"""Validate and archive device-local OCR results; never create financial entries from OCR alone."""
import json
import math
import re


def validate(conn,pid,upload,data):
    from .legal_finance_files import _row,_worker
    try: value=json.loads(data.decode('utf8'))
    except (UnicodeDecodeError,ValueError): raise ValueError('Résultat OCR JSON invalide.') from None
    keys={'schema','source_file_id','source_sha256','engine','version','language','model_sha256','pages'}
    if not isinstance(value,dict) or set(value)!=keys or value['schema']!='actelyo-ocr-v1':
        raise ValueError('Schéma de résultat OCR invalide.')
    if not isinstance(value['source_file_id'],str) or not re.fullmatch(r'[a-f0-9]{32}',value['source_file_id']) or not isinstance(value['source_sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',value['source_sha256']):
        raise ValueError('Référence source OCR invalide.')
    if value['engine']!='tesseract.js' or value['version']!='7.0.0' or value['language']!='fra' or not isinstance(value['model_sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',value['model_sha256']):
        raise ValueError('Métadonnées OCR invalides.')
    source=_row(conn,'legal_finance_files',pid,value['source_file_id'])
    if source['kind']=='ocr_result' or source['matter_id']!=upload['matter_id'] or source['sha256']!=value['source_sha256'] or upload['filename']!=f"ocr-{source['id']}.json":
        raise ValueError('Le résultat OCR ne correspond pas au document du dossier.')
    pages=value['pages']
    if not isinstance(pages,list) or not 1<=len(pages)<=20: raise ValueError('OCR limité à 20 pages.')
    if _worker(source,'inspect')['page_count']!=len(pages): raise ValueError('Le résultat OCR ne couvre pas toutes les pages du document.')
    text=[];length=0;partial=False
    for number,page in enumerate(pages,1):
        if not isinstance(page,dict) or set(page)-{'page','text','confidence'} or type(page.get('page')) is not int or page['page']!=number or not isinstance(page.get('text'),str):
            raise ValueError('Les pages OCR doivent être complètes, numérotées et ordonnées.')
        confidence=page.get('confidence')
        if confidence is not None and (type(confidence) not in (int,float) or not math.isfinite(confidence) or not 0<=confidence<=100): raise ValueError('Indice de confiance OCR invalide.')
        partial=partial or not page['text'].strip() or confidence is None or confidence<50
        length+=len(page['text'])
        if len(page['text'])>12000 or length>150000: raise ValueError('Texte OCR trop long.')
        text.append(f"[Page {number} - OCR, à vérifier]\n{page['text']}")
    if not any(p['text'].strip() for p in pages): raise ValueError('Aucun texte OCR reconnu.')
    return source,'\n\n'.join(text),'partial_ocr' if partial else 'ocr'
