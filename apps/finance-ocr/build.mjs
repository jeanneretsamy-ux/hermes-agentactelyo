import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
const root=path.dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2),option=name=>{const index=args.indexOf(name);return index<0?undefined:args[index+1]};
if(!option('--output'))throw Error('Specify --output for generated offline OCR assets.');
const output=path.resolve(option('--output'));
const pkg=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8'));
const model=JSON.parse(fs.readFileSync(path.join(root,'model-manifest.json'),'utf8'));
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const client=fs.readFileSync(path.join(root,'client.mjs'));
const clientHash=hash(client);
try{
 const previous=JSON.parse(fs.readFileSync(path.join(output,'manifest.json'),'utf8'));
 if(previous.client_sha256===clientHash&&previous.model_sha256===model.sha256&&JSON.stringify(previous.versions)===JSON.stringify(pkg.dependencies)&&previous.files.every(f=>hash(fs.readFileSync(path.join(output,f.name)))===f.sha256)){
  console.log('Offline OCR assets verified.');process.exit(0);
 }
}catch{}
const require=createRequire(import.meta.url);
const dependencyRoots=[process.cwd(),root,...(option('--deps')?[path.dirname(path.resolve(option('--deps')))]:[])];
const packages={};
for(const [name,version] of Object.entries(pkg.dependencies)){
 const manifest=require.resolve(name+'/package.json',{paths:dependencyRoots});
 const installed=JSON.parse(fs.readFileSync(manifest,'utf8'));
 if(installed.version!==version)throw Error(`OCR dependency ${name}: expected ${version}, found ${installed.version}`);
 packages[name]=path.dirname(manifest);
}
const modelPath=path.join(root,'data/fra.traineddata');
let valid=false;try{valid=hash(fs.readFileSync(modelPath))===model.sha256}catch{}
if(!valid){
 const url=new URL(model.source);
 if(url.origin!=='https://raw.githubusercontent.com'||!/^\/tesseract-ocr\/tessdata_fast\/[a-f0-9]{40}\/fra\.traineddata$/.test(url.pathname))throw Error('Unexpected OCR model source.');
 const response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(60000)});
 if(!response.ok)throw Error('Offline OCR model download failed.');
 const chunks=[];let size=0;
 for await(const chunk of response.body){size+=chunk.length;if(size>7_000_000)throw Error('OCR model too large.');chunks.push(chunk)}
 const data=Buffer.concat(chunks);
 if(size!==model.bytes||hash(data)!==model.sha256)throw Error('OCR model integrity mismatch.');
 fs.mkdirSync(path.dirname(modelPath),{recursive:true});fs.writeFileSync(modelPath,data);
}
fs.mkdirSync(output,{recursive:true});
const files=[];
function copy(source,name){
 const stat=fs.statSync(source);
 if(stat.isDirectory()){
  for(const child of fs.readdirSync(source))copy(path.join(source,child),path.posix.join(name,child));return;
 }
 const target=path.join(output,name);fs.mkdirSync(path.dirname(target),{recursive:true});
 if(args.includes('--link')){
  if(fs.existsSync(target)){if(!fs.lstatSync(target).isFile())throw Error('Unexpected generated asset target');fs.unlinkSync(target)}
  try{fs.linkSync(source,target)}catch{fs.copyFileSync(source,target)}
 }else fs.copyFileSync(source,target);
 const bytes=fs.readFileSync(target);files.push({name,bytes:bytes.length,sha256:hash(bytes)});
}
copy(path.join(root,'client.mjs'),'client.mjs');
copy(modelPath,'fra.traineddata');copy(path.join(root,'TESSDATA-LICENSE'),'licenses/TESSDATA-LICENSE');
copy(path.join(packages['tesseract.js'],'dist/tesseract.esm.min.js'),'tesseract.mjs');
copy(path.join(packages['tesseract.js'],'dist/worker.min.js'),'worker.min.js');
copy(path.join(packages['tesseract.js-core'],'tesseract-core-lstm.wasm.js'),'tesseract-core-lstm.wasm.js');
for(const name of ['tesseract.js','tesseract.js-core','pdfjs-dist']){
 const license=fs.readdirSync(packages[name]).find(file=>/^license(?:\.|$)/i.test(file));
 if(!license)throw Error(`Missing license for ${name}`);
 copy(path.join(packages[name],license),`licenses/${name}-LICENSE`);
}
for(const name of ['tesseract.min.js.LICENSE.txt','worker.min.js.LICENSE.txt'])copy(path.join(packages['tesseract.js'],'dist',name),'licenses/'+name);
copy(path.join(packages['pdfjs-dist'],'legacy/build/pdf.min.mjs'),'pdf.mjs');
copy(path.join(packages['pdfjs-dist'],'legacy/build/pdf.worker.min.mjs'),'pdf.worker.mjs');
for(const name of ['standard_fonts','cmaps','wasm','iccs'])copy(path.join(packages['pdfjs-dist'],name),name);
const manifest={language:'fra',versions:pkg.dependencies,client_sha256:clientHash,model_sha256:model.sha256,model_source:model.source,files};
fs.writeFileSync(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({offline_ocr:true,files:files.length,bytes:files.reduce((n,f)=>n+f.bytes,0)}));
