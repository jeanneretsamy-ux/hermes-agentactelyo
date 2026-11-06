"""Real PDF transfer, parsing and derivatives through typed, profile-scoped RPCs."""
import base64
import hashlib
import io
import json
from pypdf import PdfReader,PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,RectangleObject
from hermes_constants import set_hermes_home_override,reset_hermes_home_override
from tests.tui_gateway.test_legal_finance_rpc import call,denied,seed


def pdf(padding=0,rotate=False,long_text=False,blank_page=False):
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=220)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/TestFont'):font})})
    text=b'BILAN TEST 2026 - 1234 EUR '+(b'Texte source a verifier. '*1000 if long_text else b'')
    stream=DecodedStreamObject();stream.set_data(b'BT /TestFont 12 Tf 30 60 Td ('+text+b') Tj ET\n%'+b'x'*padding+b'\n')
    page[NameObject('/Contents')]=writer._add_object(stream)
    if rotate: page.rotate(90)
    if blank_page: writer.add_blank_page(width=300,height=220)
    buffer=io.BytesIO();writer.write(buffer);return buffer.getvalue()


def files(pid): return call('legal.finance.snapshot',project_id=pid)['operations']['files']


def start(pid,mid,data,request='upload'):
    return call('legal.finance.file.start',project_id=pid,request_id=request,matter_id=mid,filename='bilan-test.pdf',kind='financial_statement',size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())['upload_id']


def chunks(pid,uid,data):
    for n,offset in enumerate(range(0,len(data),36000)):
        call('legal.finance.file.chunk',project_id=pid,upload_id=uid,sequence=n,data_base64=base64.b64encode(data[offset:offset+36000]).decode())


def upload(pid,mid,data,request='upload'):
    uid=start(pid,mid,data,request);chunks(pid,uid,data)
    return call('legal.finance.file.finish',project_id=pid,upload_id=uid)


def download(pid,f):
    data=b''
    for offset in range(0,f['size_bytes'],36000):
        chunk=call('legal.finance.file.read',project_id=pid,file_id=f['id'],offset=offset)
        assert chunk['sha256']==f['sha256'] and chunk['offset']==offset
        data+=base64.b64decode(chunk['data_base64'])
    assert hashlib.sha256(data).hexdigest()==f['sha256'];return data


def test_large_pdf_chunk_retry_integrity_and_finish_replay_do_not_duplicate_documents(tmp_path):
    pid,mid=seed(tmp_path);data=pdf(padding=100000);uid=start(pid,mid,data)
    assert start(pid,mid,data)==uid
    denied('legal.finance.file.finish',project_id=pid,upload_id=uid)
    chunks(pid,uid,data);chunks(pid,uid,data)
    f=call('legal.finance.file.finish',project_id=pid,upload_id=uid)
    assert call('legal.finance.file.finish',project_id=pid,upload_id=uid)['id']==f['id']
    assert download(pid,f)==data and len(files(pid))==1
    assert upload(pid,mid,data,'same-document')['id']==f['id']
    assert len(files(pid))==1


def test_conflicting_blocks_invalid_pdf_and_out_of_scope_files_are_rejected(tmp_path):
    pid,mid=seed(tmp_path);data=pdf();uid=start(pid,mid,data)
    chunks(pid,uid,data)
    denied('legal.finance.file.chunk',project_id=pid,upload_id=uid,sequence=0,data_base64=base64.b64encode(b'x'*len(data)).decode())
    other,other_mid=seed(tmp_path/'other')
    denied('legal.finance.file.finish',project_id=other,upload_id=uid)
    f=call('legal.finance.file.finish',project_id=pid,upload_id=uid)
    denied('legal.finance.file.read',project_id=other,file_id=f['id'],offset=0)
    invalid=b'%PDF-not-a-real-document';bad=start(pid,mid,invalid,'bad');chunks(pid,bad,invalid)
    denied('legal.finance.file.finish',project_id=pid,upload_id=bad)
    assert len(files(pid))==1


def test_extract_and_stamp_create_a_new_verified_copy_while_preserving_original(tmp_path):
    pid,mid=seed(tmp_path);data=pdf(rotate=True);original=upload(pid,mid,data)
    call('legal.finance.file.extract',project_id=pid,request_id='extract',file_id=original['id'])
    text=call('legal.finance.file.text',project_id=pid,file_id=original['id'])
    assert 'BILAN TEST 2026' in text['text'] and '[Page 1]' in text['text'] and text['sha256']==original['sha256']
    prepared=call('legal.finance.prepare',project_id=pid,request_id='stamp',action='finance.file.stamp',payload={'file_id':original['id'],'piece_number':7})
    assert len(files(pid))==1
    call('legal.finance.file.stamp',project_id=pid,**prepared['params']);call('legal.finance.file.stamp',project_id=pid,**prepared['params'])
    copies=files(pid);assert len(copies)==2
    derived=next(f for f in copies if f['source_file_id']==original['id'])
    result=PdfReader(io.BytesIO(download(pid,derived)))
    assert 'BILAN TEST 2026' in result.pages[0].extract_text() and 'PIECE 007' in result.pages[0].extract_text()
    assert float(result.pages[0].mediabox.height)==328
    assert download(pid,original)==data
    denied('legal.finance.file.stamp',project_id=pid,request_id='same-number',file_id=original['id'],piece_number=7)


def test_upload_cancel_and_profile_a_b_a_never_expose_another_profiles_documents(tmp_path):
    pid,mid=seed(tmp_path);data=pdf();uid=start(pid,mid,data);chunks(pid,uid,data)
    call('legal.finance.file.cancel',project_id=pid,upload_id=uid)
    denied('legal.finance.file.finish',project_id=pid,upload_id=uid)
    source=upload(pid,mid,data,'retained')
    home=tmp_path/'profile-b';home.mkdir();token=set_hermes_home_override(home)
    try:
        denied('legal.finance.file.read',project_id=pid,file_id=source['id'],offset=0)
        other,_=seed(home);assert not files(other)
    finally: reset_hermes_home_override(token)
    assert download(pid,source)==data


def test_agent_reads_all_source_parts_with_hash_provenance_and_cannot_override_scope(tmp_path):
    from tools.legal_cabinet import legal_cabinet
    pid,mid=seed(tmp_path);original=upload(pid,mid,pdf(long_text=True,blank_page=True))
    call('legal.finance.file.extract',project_id=pid,request_id='extract',file_id=original['id'])
    whole=call('legal.finance.file.text',project_id=pid,file_id=original['id'])
    assert whole['untrusted'] is True and whole['mode']=='partial_text'
    collected='';offset=0
    while True:
        reply=json.loads(legal_cabinet('finance.file.text',project=pid,operation_payload={'file_id':original['id']},document_offset=offset))
        assert reply['success'],reply
        part=reply['data'];assert part['sha256']==original['sha256'] and part['untrusted'] is True
        collected+=part['text']
        if not part['truncated']:break
        assert part['next_offset']>offset;offset=part['next_offset']
    assert collected==whole['text'] and offset>0
    denied_result=json.loads(legal_cabinet('finance.file.text',project=pid,operation_payload={'file_id':original['id'],'project_id':'other'}))
    assert not denied_result['success']
