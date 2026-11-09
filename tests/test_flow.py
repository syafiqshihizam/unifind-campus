"""End-to-end HTTP tests using only the Python standard library."""
import http.cookiejar
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TMP = tempfile.TemporaryDirectory()
os.environ['CAMPUSBACK_DB'] = str(Path(TMP.name) / 'test.db')
os.environ['CAMPUSBACK_UPLOADS'] = str(Path(TMP.name) / 'uploads')
from server import CampusHandler, ThreadingHTTPServer, init_db  # noqa: E402


class Client:
    def __init__(self, url):
        self.url = url
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None

    def get(self, path):
        return self.request(path)

    def request(self, path, method='GET', data=None, multipart=False):
        headers = {}
        if method != 'GET' and self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        if multipart:
            boundary = '----test' + uuid.uuid4().hex
            payload = bytearray()
            for k, value in data.items():
                payload += f'--{boundary}\r\n'.encode()
                if isinstance(value, tuple):
                    fn, contents, mime = value
                    payload += f'Content-Disposition: form-data; name="{k}"; filename="{fn}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + contents + b'\r\n'
                else:
                    payload += f'Content-Disposition: form-data; name="{k}"\r\n\r\n{value}\r\n'.encode()
            payload += f'--{boundary}--\r\n'.encode()
            body = bytes(payload)
            headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
        elif data is not None:
            body = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        else:
            body = None
        req = urllib.request.Request(self.url + path, data=body, method=method, headers=headers)
        try:
            resp = self.opener.open(req, timeout=8)
        except urllib.error.HTTPError as e:
            resp = e
        contents = resp.read()
        if path == '/':
            return resp.code, contents
        obj = json.loads(contents)
        return resp.code, obj

    def register(self, name):
        email = f'{name.lower()}@example.test'
        code, _ = self.request('/api/register', 'POST', {'name':name,'email':email,'password':'StrongPassword123!'})
        assert code == 201
        code, session = self.get('/api/session')
        assert code == 200 and session['authenticated']
        self.csrf = session['csrf_token']
        return session['user']['id']

    def report(self, kind, **overrides):
        data = dict(kind=kind, name='Black wallet', category='Wallet', color='Black', location='Library',
                    event_date=date.today().isoformat(), description='Small black leather wallet with a star keychain')
        if kind == 'found':
            data.update(question='How many cards?', answer='3', handover='Student Affairs Office')
        data.update(overrides)
        return self.request('/api/items','POST',data,multipart=True)


class FullFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), CampusHandler)
        cls.address = f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        TMP.cleanup()

    def test_01_home_and_accounts(self):
        client = Client(self.address)
        code, html = client.get('/')
        self.assertEqual(code, 200)
        self.assertIn(b'CampusBack', html)
        code, public = client.get('/api/items')
        self.assertEqual(code, 200)
        self.assertIsInstance(public['items'], list)
        client.register('Alice')
        code, _ = client.request('/api/register','POST',{'name':'Another Alice','email':'alice@example.test','password':'12345678'})
        self.assertEqual(code, 409)

    def test_02_matching_claims_and_handover(self):
        loser = Client(self.address)
        finder = Client(self.address)
        stranger = Client(self.address)
        loser.register('Owner')
        finder.register('Finder')
        stranger.register('Stranger')
        code, lost = loser.report('lost')
        self.assertEqual(code, 201, lost)
        code, found = finder.report('found', photo=('test.png', b'\x89PNG\r\n\x1a\n' + b'abc', 'image/png'))
        self.assertEqual(code, 201, found)
        found_id, lost_id = found['id'], lost['id']
        code, matches = loser.get('/api/matches')
        self.assertEqual(code, 200)
        pair = next(m for m in matches['matches'] if m['found']['id'] == found_id)
        self.assertGreaterEqual(pair['score'], 65)
        self.assertEqual(pair['found']['verification_question'],'How many cards?')
        self.assertNotIn('verification_hash', pair['found'])
        code, search = loser.get('/api/items?kind=found&q=wallet')
        self.assertEqual(code, 200)
        self.assertTrue(any(i['id']==found_id for i in search['items']))
        self.assertNotIn('verification_hash', search['items'][0])
        code, bad_claim = stranger.request('/api/claims','POST',{'found_id':found_id,'lost_id':lost_id,'answer':'3'})
        self.assertEqual(code, 403, bad_claim)
        code, bad = loser.request('/api/claims','POST',{'found_id':found_id,'lost_id':lost_id,'answer':'4'})
        self.assertEqual(code, 403, bad)
        code, success = loser.request('/api/claims','POST',{'found_id':found_id,'lost_id':lost_id,'answer':' 3 '})
        self.assertEqual(code, 201, success)
        self.assertEqual(success['handover_location'],'Student Affairs Office')
        code, claimed_again = loser.request('/api/claims','POST',{'found_id':found_id,'lost_id':lost_id,'answer':'3'})
        self.assertEqual(code, 409, claimed_again)
        claim_id = success['claim_id']
        code, denied = loser.request(f'/api/claims/{claim_id}/complete','POST',{})
        self.assertEqual(code, 403, denied)
        code, done = finder.request(f'/api/claims/{claim_id}/complete','POST',{})
        self.assertEqual(code, 200, done)
        code, stats = finder.get('/api/stats')
        self.assertGreaterEqual(stats['returned'], 1)
        code, claims = loser.get('/api/claims')
        self.assertTrue(any(c['status']=='returned' for c in claims['claims']))

    def test_03_validation_auth_and_upload(self):
        anonymous = Client(self.address)
        code, err = anonymous.get('/api/matches')
        self.assertEqual(code, 401)
        client = Client(self.address)
        client.register('Tester')
        client.csrf = 'wrongtoken'
        code, fail = client.report('lost')
        self.assertEqual(code, 403)
        client.get('/api/session')
        # reset from server
        client.csrf = client.get('/api/session')[1]['csrf_token']
        code, err = client.report('lost', photo=('bad.exe', b'NOT AN IMAGE','application/octet-stream'))
        self.assertEqual(code, 400, err)
        code, err = client.report('found', answer='')
        self.assertEqual(code, 400, err)
        code, good = client.report('lost')
        self.assertEqual(code, 201, good)
        code, result = client.request('/api/logout','POST',{})
        self.assertEqual(code, 200)
        code, session = client.get('/api/session')
        self.assertFalse(session['authenticated'])


if __name__ == '__main__':
    unittest.main()
