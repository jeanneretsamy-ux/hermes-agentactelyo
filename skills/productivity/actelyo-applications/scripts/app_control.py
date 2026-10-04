"""Operate an observed Actelyo window over an explicitly enabled loopback CDP connection."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import time
from urllib.parse import urlparse

from desktop_link import read_endpoint


def target_for(port: int, target_id: str | None) -> dict:
    targets = read_endpoint(port, 'json/list')
    pages = [p for p in targets if p.get('type') == 'page' and 'actelyo' in p.get('title', '').lower()]
    if target_id:
        pages = [p for p in pages if p['id'] == target_id]
    if len(pages) != 1:
        raise ValueError('Select exactly one observed Actelyo window using --target. Run desktop_link.py probe first.')
    target = pages[0]
    parsed = urlparse(target.get('url', ''))
    if not (parsed.scheme == 'file' or parsed.hostname in {'actelyo.com', 'www.actelyo.com', '127.0.0.1', 'localhost', '::1'}):
        raise ValueError('The observed window is outside the supported Actelyo web/local origins.')
    endpoint = urlparse(target['webSocketDebuggerUrl'])
    if endpoint.hostname not in {'127.0.0.1', 'localhost', '::1'}:
        raise ValueError('CDP must remain on loopback.')
    return target


def request(ws, method: str, params: dict) -> dict:
    ws.send(json.dumps({'id': 1, 'method': method, 'params': params}))
    while True:
        result = json.loads(ws.recv(timeout=15))
        if result.get('id') == 1:
            if 'error' in result:
                raise RuntimeError(result['error']['message'])
            return result['result']


def evaluate(ws, expression: str):
    result = request(ws, 'Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
    if 'exceptionDetails' in result:
        raise RuntimeError(result['exceptionDetails'].get('exception', {}).get('description', 'UI operation failed.'))
    return result['result'].get('value')


SNAPSHOT = """(() => {
 const prefix = Date.now().toString(36);
 const controls = [...document.querySelectorAll('a,button,input,textarea,select,[role="button"]')]
  .filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden')
  .map((e,i) => { const ref=prefix+'-'+i; e.dataset.actelyoAgentRef=ref;
   return {ref,tag:e.tagName.toLowerCase(),label:e.getAttribute('aria-label')||e.innerText||e.getAttribute('placeholder')||e.name||'',type:e.type||'',disabled:!!e.disabled}; });
 return {title:document.title,url:location.href,text:document.body.innerText,controls};
})()"""


def control(port: int, target_id: str | None, action: str, ref: str | None = None,
            text: str | None = None, output: Path | None = None) -> dict:
    from websockets.sync.client import connect
    target = target_for(port, target_id)
    with connect(target['webSocketDebuggerUrl'], open_timeout=10, max_size=30_000_000) as ws:
        if action in {'click', 'fill'}:
            if not ref:
                raise ValueError('Use a reference returned by the latest snapshot.')
            selector = '[data-actelyo-agent-ref=' + json.dumps(ref) + ']'
            expression = "(() => {const e=document.querySelector("+json.dumps(selector)+");if(!e||!e.getClientRects().length||e.disabled)throw new Error('Reference is absent, hidden or disabled; take a new snapshot.');"
            if action == 'click':
                expression += "e.click();return true;})()"
            else:
                expression += "if(e.type==='password')throw new Error('Enter passwords manually in the app.');if(!['INPUT','TEXTAREA'].includes(e.tagName))throw new Error('Reference is not a text input.');const p=e.tagName==='INPUT'?HTMLInputElement.prototype:HTMLTextAreaElement.prototype;Object.getOwnPropertyDescriptor(p,'value').set.call(e,"+json.dumps(text or '')+");e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()"
            evaluate(ws, expression)
            time.sleep(1)
        if action == 'screenshot':
            if output is None:
                raise ValueError('--output is required for screenshots.')
            result = request(ws, 'Page.captureScreenshot', {'format': 'png'})
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(base64.b64decode(result['data']))
            return {'target': target['id'], 'screenshot': str(output.resolve())}
        return {'target': target['id'], 'action': action, 'observed': evaluate(ws, SNAPSHOT)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'click', 'fill', 'screenshot'])
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--target')
    parser.add_argument('--ref')
    parser.add_argument('--text')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(control(args.port, args.target, args.action, args.ref, args.text, args.output), ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
        print(json.dumps({'status': 'unavailable', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
