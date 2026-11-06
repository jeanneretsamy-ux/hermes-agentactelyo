"""OCR receipts retain the immutable PDF and cannot cross matter boundaries."""
import hashlib
import json

from tests.tui_gateway.test_legal_finance_rpc import call,denied,seed
from tests.tui_gateway.test_legal_finance_files_rpc import chunks,download,files,pdf,upload


def receipt(source,text='Honoraires 1234 euros',confidence=95):
    return dict(schema='actelyo-ocr-v1',source_file_id=source['id'],source_sha256=source['sha256'],
                engine='tesseract.js',version='7.0.0',language='fra',model_sha256='c'*64,
                pages=[dict(page=1,text=text,confidence=confidence)])


def start_ocr(pid,mid,source,value,request):
    data=json.dumps(value).encode()
    result=call('legal.finance.file.start',project_id=pid,request_id=request,matter_id=mid,
                filename=f"ocr-{source['id']}.json",kind='ocr_result',size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    chunks(pid,result['upload_id'],data)
    return result['upload_id']


def test_ocr_receipts_preserve_pdf_hash_and_completed_replay_does_not_replace_newer_text(tmp_path):
    pid,mid=seed(tmp_path);data=pdf();source=upload(pid,mid,data)
    first=start_ocr(pid,mid,source,receipt(source),'ocr-first')
    saved=call('legal.finance.file.finish',project_id=pid,upload_id=first)
    text=call('legal.finance.file.text',project_id=pid,file_id=source['id'])
    assert text['mode']=='ocr' and text['extraction_source_id']==saved['id'] and text['untrusted'] is True
    assert '1234' in text['text'] and text['sha256']==source['sha256']
    second=start_ocr(pid,mid,source,receipt(source,'Frais 250 euros',confidence=30),'ocr-second')
    newer=call('legal.finance.file.finish',project_id=pid,upload_id=second)
    call('legal.finance.file.finish',project_id=pid,upload_id=first)
    current=call('legal.finance.file.text',project_id=pid,file_id=source['id'])
    assert current['mode']=='partial_ocr' and current['extraction_source_id']==newer['id'] and '250' in current['text']
    assert download(pid,source)==data and len(files(pid))==3


def test_invalid_source_hash_page_coverage_and_other_matter_never_modify_pdf_text(tmp_path):
    pid,mid=seed(tmp_path);source=upload(pid,mid,pdf())
    bad_hash=receipt(source);bad_hash['source_sha256']='0'*64
    bad_pages=receipt(source);bad_pages['pages'].append(dict(page=2,text='extra',confidence=99))
    bad_confidence=receipt(source);bad_confidence['pages'][0]['confidence']=float('nan')
    for number,value in enumerate([bad_hash,bad_pages,bad_confidence]):
        uid=start_ocr(pid,mid,source,value,f'invalid-{number}')
        denied('legal.finance.file.finish',project_id=pid,upload_id=uid)
        call('legal.finance.file.cancel',project_id=pid,upload_id=uid)
    other,other_mid=seed(tmp_path/'other')
    uid=start_ocr(other,other_mid,source,receipt(source),'foreign-source')
    denied('legal.finance.file.finish',project_id=other,upload_id=uid)
    assert len(files(pid))==1
    text=call('legal.finance.file.text',project_id=pid,file_id=source['id'])
    assert text['text']=='' and text['mode']=='not_requested' and text['extraction_source_id'] is None
