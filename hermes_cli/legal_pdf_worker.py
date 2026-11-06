"""Bounded, local PDF worker. No model, network request or document instruction execution."""
import base64
import io
import json
import sys


def _limit_memory():
    if sys.platform!='win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(768*1024*1024,768*1024*1024))
        return
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',wintypes.DWORD),
                  ('min_working',ctypes.c_size_t),('max_working',ctypes.c_size_t),('processes',wintypes.DWORD),
                  ('affinity',ctypes.c_size_t),('priority',wintypes.DWORD),('scheduling',wintypes.DWORD)]
    class Io(ctypes.Structure):
        _fields_=[(name,ctypes.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(ctypes.Structure):
        _fields_=[('basic',Basic),('io',Io),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                  ('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR];kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    limits=Extended();limits.basic.flags=0x100|0x2000;limits.process_memory=768*1024*1024
    if not job or not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        raise ValueError('Isolation mémoire du traitement PDF indisponible.')
    # The OS retains the handle until this short-lived worker exits.


def _reader(data):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data),strict=True)
    if reader.is_encrypted: raise ValueError('PDF chiffré : fournir une copie déchiffrée autorisée.')
    if not 0<len(reader.pages)<=100: raise ValueError('PDF limité à 100 pages par traitement.')
    for page in reader.pages:
        content=page.get_contents()
        if content is not None and len(content.get_data())>2_000_000: raise ValueError('Page trop complexe pour le traitement local.')
        resources=page.get('/Resources');seen=set();pixels=[0]
        if resources is not None: _check_images(resources.get_object(),seen,pixels)
    return reader


def _check_images(resources,seen,pixels,depth=0):
    if depth>8 or len(seen)>2000: raise ValueError('Structure graphique PDF trop complexe.')
    objects=resources.get('/XObject')
    if objects is None: return
    for reference in objects.get_object().values():
        obj=reference.get_object()
        if id(obj) in seen: continue
        seen.add(id(obj))
        if obj.get('/Subtype')=='/Image':
            count=int(obj.get('/Width',0))*int(obj.get('/Height',0));pixels[0]+=count
            if count<=0 or count>12_000_000 or pixels[0]>24_000_000: raise ValueError('Images PDF trop grandes pour le traitement local.')
        elif obj.get('/Subtype')=='/Form' and obj.get('/Resources') is not None:
            _check_images(obj['/Resources'],seen,pixels,depth+1)


def _extract(data):
    reader=_reader(data);pages=[];length=0
    for number,page in enumerate(reader.pages,1):
        content=page.get_contents()
        if content is not None and len(content.get_data())>2_000_000: raise ValueError('Page trop complexe pour l’extraction locale.')
        text=page.extract_text() or ''
        length+=len(text)
        if length>150000: raise ValueError('Texte trop long : fractionner le document.')
        pages.append({'page':number,'text':text})
    if not any(p['text'].strip() for p in pages):
        raise ValueError('PDF image : aucun texte extractible. Un moteur OCR local est nécessaire.')
    return {'mode':'partial_text' if any(not p['text'].strip() for p in pages) else 'text','pages':pages,'text':'\n\n'.join(f"[Page {p['page']}]\n{p['text']}" for p in pages)}


def _stamp(data,number):
    from pypdf import PdfWriter,Transformation
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    reader=_reader(data);writer=PdfWriter();original_texts=[]
    if reader.get_fields(): raise ValueError('PDF formulaire ou signé : fournir une copie imprimable avant tamponnage.')
    for index,source in enumerate(reader.pages,1):
        if source.get('/Annots'): raise ValueError('PDF annoté : fournir une copie imprimable pour préserver les annotations.')
        original_content=source.get_contents()
        if original_content is not None and len(original_content.get_data())>2_000_000: raise ValueError('Page trop complexe pour le tamponnage local.')
        original_texts.append(' '.join((source.extract_text() or '').split()))
        source.transfer_rotation_to_content()
        crop=source.cropbox
        width,height=float(crop.width),float(crop.height)
        if not 50<=width<=2000 or not 50<=height<=2000: raise ValueError('Dimensions de page non prises en charge.')
        # New footer outside the original crop area: never cover the evidence text.
        page=writer.add_blank_page(width=width,height=height+28)
        page.merge_transformed_page(source,Transformation().translate(-float(crop.left),28-float(crop.bottom)))
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        resources=page.get('/Resources') or DictionaryObject()
        fonts=resources.get('/Font') or DictionaryObject()
        fonts[NameObject('/ActelyoPiece')]=writer._add_object(font)
        resources[NameObject('/Font')]=fonts
        page[NameObject('/Resources')]=resources
        text=f'PIECE {number:03d} | page {index}/{len(reader.pages)} | ACTELYO'
        stamp=DecodedStreamObject()
        stamp.set_data(f'q 0.5 G 0 27 m {width:.3f} 27 l S 0 g BT /ActelyoPiece 9 Tf 12 9 Td ({text}) Tj ET Q'.encode('ascii'))
        current=page.get_contents()
        joined=DecodedStreamObject()
        joined.set_data((current.get_data() if current is not None else b'')+b'\n'+stamp.get_data())
        page[NameObject('/Contents')]=writer._add_object(joined)
    writer.add_metadata({'/Producer':'Actelyo - copie de piece','/Title':f'Piece {number:03d}'})
    buffer=io.BytesIO();writer.write(buffer)
    result=buffer.getvalue()
    if len(result)>5_000_000: raise ValueError('Copie tamponnée trop volumineuse.')
    verify=_reader(result)
    if len(verify.pages)!=len(reader.pages) or any(f'PIECE {number:03d}' not in (p.extract_text() or '') for p in verify.pages):
        raise ValueError('Vérification du tampon impossible.')
    if any(text and text not in ' '.join((page.extract_text() or '').split()) for text,page in zip(original_texts,verify.pages)):
        raise ValueError('La vérification du texte original a échoué ; copie refusée.')
    return {'data_base64':base64.b64encode(result).decode(),'page_count':len(verify.pages)}


def main():
    request=json.loads(sys.stdin.buffer.read(7_000_000))
    data=base64.b64decode(request['data_base64'],validate=True)
    if not data.startswith(b'%PDF-') or len(data)>5_000_000: raise ValueError('PDF invalide ou trop volumineux.')
    if request['operation']=='inspect': return {'page_count':len(_reader(data).pages)}
    if request['operation']=='extract': return _extract(data)
    if request['operation']=='stamp' and type(request.get('piece_number')) is int and 1<=request['piece_number']<=999999:
        return _stamp(data,request['piece_number'])
    raise ValueError('Traitement PDF non autorisé.')


if __name__=='__main__':
    try:
        _limit_memory()
        print(json.dumps({'ok':True,'result':main()},ensure_ascii=False))
    except ImportError: print(json.dumps({'ok':False,'error':'Module PDF local absent : installer les dépendances finance du Law Harness.'}));sys.exit(1)
    except ValueError as error: print(json.dumps({'ok':False,'error':str(error)}));sys.exit(1)
    except Exception: print(json.dumps({'ok':False,'error':'Document PDF non pris en charge ; original conservé.'}));sys.exit(1)
