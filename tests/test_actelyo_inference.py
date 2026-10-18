import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from hermes_cli.local_runtime import inference_check, bootstrap, endpoint


def test_real_http_completion_and_empty_response(monkeypatch):
    observed = []
    replies = ['ACTELYO_OK', 'Autre réponse', '']
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            observed.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({'choices':[{'message':{'content':replies.pop(0)}}]}).encode())
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    monkeypatch.setattr(bootstrap,'staged_model_ids',lambda:['fixture'])
    monkeypatch.setattr(endpoint,'_state_endpoint',lambda:{'base_url':f'http://127.0.0.1:{server.server_port}/v1'})
    try:
        assert inference_check.check('fixture')['instruction_followed']
        assert not inference_check.check('fixture')['instruction_followed']
        with pytest.raises(ValueError,match='aucun texte'):
            inference_check.check('fixture')
        with pytest.raises(ValueError,match='absent'):
            inference_check.check('missing')
        assert len(observed)==3
        assert observed[0][0]=='/v1/chat/completions'
        assert observed[0][1]['model']=='fixture'
        assert observed[0][1]['stream'] is False
        from tools.registry import registry
        import tools.actelyo_studio  # noqa: F401
        replies.append('ACTELYO_OK')
        started = json.loads(registry.dispatch('actelyo_studio', {'action':'test_inference','model_id':'fixture'}))
        assert started['success']
        limit = time.monotonic() + 10
        while time.monotonic() < limit:
            job = json.loads(registry.dispatch('actelyo_studio', {'action':'job','job_id':started['data']['job_id']}))
            if job['data']['status'] in ('done','error'):
                break
            time.sleep(.02)
        assert job['data']['status']=='done', job
        assert 'Consigne respectée' in job['data']['detail']

    finally:
        server.shutdown()
        server.server_close()
        thread.join()
