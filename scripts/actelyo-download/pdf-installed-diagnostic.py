"""Inspect the real installed worker using synthetic data; never alter the installed files."""
import base64,json,os,runpy,site,subprocess,sys,traceback
from pathlib import Path

payload=Path(sys.argv[1]).resolve();fixture=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve()
manifest=json.loads((payload/'manifest.json').read_text(encoding='utf-8-sig'))
runtime=manifest['runtime']
def owned(name):
 path=(payload/runtime[name]).resolve()
 if not path.is_relative_to(payload) or not path.exists():raise RuntimeError('Installed runtime path escaped.')
 return path
repo=owned('repoDir');packages=owned('sitePackages');python=owned('storePython')
sys.path.insert(0,str(repo));site.addsitedir(str(packages))
os.environ.pop('PYTHONPATH',None);os.environ.pop('PYTHONHOME',None)
os.environ['HERMES_HOME']=str(out/'synthetic-home');(out/'synthetic-home').mkdir(parents=True,exist_ok=True)
from tools.environments.local import served_profile_child_env
env=served_profile_child_env()
worker=repo/'hermes_cli/legal_pdf_worker.py'
request={'operation':'inspect','data_base64':base64.b64encode(fixture.read_bytes()).decode()}
result={'python_version':sys.version,'runtime':runtime,'fixture_bytes':fixture.stat().st_size,'synthetic_only':True,'installed_files_modified':False}
try:
 import pypdf
 result['parent_pypdf']={'version':pypdf.__version__,'file':str(Path(pypdf.__file__).relative_to(payload))}
except Exception:
 result['parent_pypdf_error']=traceback.format_exc()
original=subprocess.run([str(python),str(worker)],input=json.dumps(request),text=True,capture_output=True,timeout=45,env=env)
result['original_worker']={'exit':original.returncode,'stdout':original.stdout[-16000:],'stderr':original.stderr[-16000:]}
code="""import sys,json,base64,runpy,traceback
from pathlib import Path
worker=Path(sys.argv[1]);sys.path[0]=str(worker.parent)
ns=runpy.run_path(str(worker),run_name='pdf_diagnostic')
phase='limits'
try:
 ns['_limit_memory']()
 phase='reader'
 request=json.load(sys.stdin)
 answer=ns['_reader'](base64.b64decode(request['data_base64']))
 print(json.dumps({'ok':True,'pages':len(answer.pages)}))
except BaseException as error:
 print(json.dumps({'ok':False,'phase':phase,'type':type(error).__name__,'message':str(error),'trace':traceback.format_exc()}))
"""
for mode,prelude in [('bare',''),('explicit-installed-dependencies',f'import sys,site;sys.path.insert(0,{str(repo)!r});site.addsitedir({str(packages)!r});')]:
 args=[str(python),'-c',prelude+code,str(worker)]
 diagnostic=subprocess.run(args,input=json.dumps(request),text=True,capture_output=True,timeout=45,env=env)
 result[mode]={'exit':diagnostic.returncode,'stdout':diagnostic.stdout[-16000:],'stderr':diagnostic.stderr[-16000:]}
out.mkdir(exist_ok=True)
(out/'pdf-diagnostic.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in result.items() if k!='runtime'},indent=2))
