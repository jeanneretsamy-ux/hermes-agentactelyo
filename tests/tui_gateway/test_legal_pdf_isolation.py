"""A PDF worker must use selected dependencies even from an isolated launcher."""
import json
from pathlib import Path
import subprocess
import sys

import pypdf


def test_pdf_worker_uses_selected_dependencies_and_ignores_foreign_pythonpath(tmp_path):
    import os
    from hermes_cli import legal_finance_files
    root=Path(legal_finance_files.__file__).resolve().parents[1]
    fixture=root/'scripts/actelyo-download/fixtures/finance-scan.pdf'
    foreign=tmp_path/'foreign';foreign.mkdir()
    (foreign/'pypdf.py').write_text('raise RuntimeError("FOREIGN_PDF_MUST_NOT_RUN")\n',encoding='utf8')
    home=tmp_path/'profile';home.mkdir()
    program='''import json,site,sys
site.addsitedir(sys.argv[2])
sys.path.insert(0,sys.argv[1])
from hermes_cli.legal_finance_files import _worker
from pathlib import Path
print(json.dumps(_worker({'data':Path(sys.argv[3]).read_bytes()},'inspect')))
'''
    env={**os.environ,'PYTHONPATH':str(foreign),'HERMES_HOME':str(home),'PYTHONUTF8':'1'}
    process=subprocess.run([sys.executable,'-I','-S','-X','utf8','-c',program,str(root),str(Path(pypdf.__file__).resolve().parents[1]),str(fixture)],
                           env=env,capture_output=True,text=True,timeout=45)
    assert process.returncode==0,process.stderr
    assert json.loads(process.stdout)=={'page_count':1}
