// Application-owned entry point. Every engine, worker, font and language file is local.
import Tesseract from './tesseract.mjs';
const {createWorker}=Tesseract;
import * as pdfjs from './pdf.mjs';
pdfjs.GlobalWorkerOptions.workerSrc=new URL('./pdf.worker.mjs',import.meta.url).href;

export async function recognizePdf(bytes,{signal,onProgress=()=>{}}={}){
 const base=new URL('./',import.meta.url);
 const response=await fetch(new URL('manifest.json',base),{signal});
 if(!response.ok)throw Error('Moteur OCR local absent. Mettre l’application à jour.');
 const manifest=await response.json();
 if(manifest.language!=='fra'||manifest.versions['tesseract.js']!=='7.0.0'||manifest.versions['pdfjs-dist']!=='6.4.299')throw Error('Version OCR locale incompatible.');
 let worker,document,renderTask,interrupted;
 let rejectInterrupt;
 const interruption=new Promise((_,reject)=>{rejectInterrupt=reject});
 const wait=promise=>Promise.race([promise,interruption]);
 const loading=pdfjs.getDocument({data:new Uint8Array(bytes),isEvalSupported:false,disableFontFace:true,
  useSystemFonts:true,cMapUrl:new URL('cmaps/',base).href,cMapPacked:true,
  standardFontDataUrl:new URL('standard_fonts/',base).href,wasmUrl:new URL('wasm/',base).href,
  iccUrl:new URL('iccs/',base).href,disableAutoFetch:true,disableStream:true});
 const abort=()=>{interrupted=Error(signal?.aborted?'OCR annulé.':'Délai OCR dépassé.');rejectInterrupt(interrupted);renderTask?.cancel();void worker?.terminate();void loading.destroy()};
 signal?.addEventListener('abort',abort,{once:true});
 const timer=setTimeout(abort,120000);
 try{
  if(signal?.aborted)throw Error('OCR annulé.');
  document=await wait(loading.promise);
  if(document.numPages>20)throw Error('OCR local limité à 20 pages par document.');
  worker=await wait(createWorker('fra',1,{workerPath:new URL('worker.min.js',base).href,
    corePath:new URL('tesseract-core-lstm.wasm.js',base).href,langPath:base.href,
    gzip:false,workerBlobURL:false,cacheMethod:'none'}).then(value=>{if(interrupted)void value.terminate();return value}));
  await wait(worker.setParameters({preserve_interword_spaces:'1'}));
  const pages=[];let characters=0;
  for(let number=1;number<=document.numPages;number++){
   if(signal?.aborted)throw Error('OCR annulé.');
   const page=await wait(document.getPage(number)),original=page.getViewport({scale:1});
   const scale=Math.min(2,Math.sqrt(2_500_000/(original.width*original.height)));
   const viewport=page.getViewport({scale}),canvas=globalThis.document.createElement('canvas');
   canvas.width=Math.ceil(viewport.width);canvas.height=Math.ceil(viewport.height);
   const context=canvas.getContext('2d',{willReadFrequently:true});if(!context)throw Error('Rendu OCR indisponible.');
   try{
    renderTask=page.render({canvasContext:context,canvas,viewport});await wait(renderTask.promise);
    const result=await wait(worker.recognize(canvas,{}, {text:true}));
    const text=result.data.text||'';characters+=text.length;
    if(text.length>12000||characters>150000)throw Error('Texte OCR trop long ; fractionner le document.');
    pages.push({page:number,text,confidence:result.data.confidence});onProgress(number,document.numPages);
   }finally{canvas.width=0;canvas.height=0;page.cleanup();renderTask=null}
  }
  if(!pages.some(p=>p.text.trim()))throw Error('Aucun texte reconnu dans ce document.');
  return {engine:'tesseract.js',version:'7.0.0',language:'fra',model_sha256:manifest.model_sha256,pages};
 }finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);await worker?.terminate().catch(()=>{});await loading.destroy().catch(()=>{})}
}
