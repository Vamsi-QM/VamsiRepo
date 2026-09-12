"""Independent acceptance: unique database, real inference, restart, proven retrieval."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    run = ROOT / 'cache' / 'acceptance' / uuid.uuid4().hex
    run.mkdir(parents=True)
    database = run / 'acceptance.db'
    existing = ROOT / 'data' / 'companion.db'
    before = hashlib.sha256(existing.read_bytes()).hexdigest() if existing.exists() else None
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    env = dict(os.environ, HOST='127.0.0.1', PORT=str(port), DATA_DIR=str(run),
               DB_NAME=database.name, PYTHONIOENCODING='utf-8', MAX_TOKENS='128')
    def post(message, cid=None, rid=None):
        start = time.monotonic()
        req = urllib.request.Request(base+'/api/chat',
            data=json.dumps(dict(message=message, conversation_id=cid, request_id=rid or uuid.uuid4().hex)).encode(),
            headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=200) as response:
            result = json.load(response)
        print(json.dumps({'message':message, 'response':result, 'elapsed':round(time.monotonic()-start,2)}), flush=True)
        assert result['ok'], result
        return result
    log = (run/'server.log').open('w',encoding='utf-8')
    proc = None
    def start():
        child = subprocess.Popen([sys.executable,'-m','app.main'],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(100):
            if child.poll() is not None:
                raise RuntimeError('Server exited; see '+str(run/'server.log'))
            try:
                with urllib.request.urlopen(base+'/api/health',timeout=1) as response:
                    assert json.load(response)['model_available']
                    return child
            except OSError:
                time.sleep(.1)
        child.terminate(); child.wait()
        raise RuntimeError('server did not start')
    try:
        proc=start()
        # Must use actual inference, not a note-command shortcut.
        greeting=post('Say hello in one short sentence.')
        assert greeting['reply'].strip() and not greeting['tool_calls']
        token='Orchid-'+uuid.uuid4().hex[:10]
        saved=post('Save a note: my project is called '+token+'.',greeting['conversation_id'])
        assert saved['tool_calls'][0]['tool']=='save_note'
        with sqlite3.connect(database) as conn:
            rows=conn.execute('select content from notes').fetchall()
        assert rows==[('my project is called '+token+'.',)], rows
        same=post('What is my project called?',saved['conversation_id'])
        assert token in same['reply'] and same['tool_calls'][0]['tool']=='find_notes'
        proc.terminate();proc.wait(timeout=15)
        proc=start()
        retrieved=post('What is my project called?')
        assert token in retrieved['reply'] and retrieved['tool_calls'][0]['tool']=='find_notes'
        absent=post('Find notes: nonexistent-'+uuid.uuid4().hex,retrieved['conversation_id'])
        assert "couldn't find" in absent['reply']
        # Warm real-model turn after restart also must work.
        post('Explain in one short sentence what a rainbow is.',retrieved['conversation_id'])
        after=hashlib.sha256(existing.read_bytes()).hexdigest() if existing.exists() else None
        assert before==after, 'Everyday database changed'
        print('E2E PASS; isolated evidence: '+str(run),flush=True)
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate();proc.wait(timeout=15)
        log.close()

if __name__=='__main__':
    main()
