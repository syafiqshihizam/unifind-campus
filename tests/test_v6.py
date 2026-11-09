"""End-to-end V6 API tests using only Python standard library."""
import os, sys, tempfile, subprocess, time, http.cookiejar, urllib.request, urllib.error, json
from pathlib import Path
base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    env=os.environ.copy();env['CAMPUSBACK_DB']=str(Path(folder)/'state.db');env['CAMPUSBACK_UPLOADS']=str(Path(folder)/'uploads');env['PORT']='18749'
    p=subprocess.run([sys.executable,'seed_demo.py'],cwd=base,env=env,capture_output=True,text=True)
    assert p.returncode==0,(p.stdout,p.stderr)
    proc=subprocess.Popen([sys.executable,'server.py'],cwd=base,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    root='http://127.0.0.1:18749'
    def client():
        c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));c.csrf=None;return c
    def req(c,path,data=None,method='GET'):
        headers={};raw=None
        if method=='POST':
            raw=json.dumps(data or {}).encode();headers['Content-Type']='application/json'
            if c.csrf:headers['X-CSRF-Token']=c.csrf
        q=urllib.request.Request(root+path,raw,headers=headers,method=method)
        try:
            with c.open(q,timeout=5) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def login(c,email):
        code,d=req(c,'/api/login',{'email':email,'password':'Demo1234!'},'POST');assert code==200,(code,d)
        code,d=req(c,'/api/session');assert code==200,(code,d);c.csrf=d['csrf_token'];return d
    try:
        for _ in range(50):
            try:
                if req(client(),'/api/items')[0]==200:break
            except Exception:time.sleep(.1)
        sara,daniel,staff,guest=client(),client(),client(),client()
        assert login(sara,'sara@campus.test')['user']['is_staff'] is False
        assert login(daniel,'daniel@campus.test')['user']['is_staff'] is False
        assert login(staff,'counter@campus.test')['user']['is_staff'] is True
        code,found=req(guest,'/api/items');assert code==200 and len(found['items'])==4,found
        assert all(x['kind']=='found' for x in found['items'])
        code,lost=req(guest,'/api/items?kind=lost');assert code==200 and len(lost['items'])==4,lost
        wallet=next(x for x in found['items'] if 'Wallet' in x['name'])
        earbud=next(x for x in found['items'] if 'Earbuds' in x['name'])
        keys=next(x for x in found['items'] if 'Keys' in x['name'])
        bag=next(x for x in found['items'] if 'Backpack' in x['name'])
        # staff must not be allowed to act as student, finder cannot request own item
        assert req(staff,'/api/pickups',{'found_id':wallet['id'],'method':'meet'},'POST')[0]==403
        assert req(daniel,'/api/pickups',{'found_id':wallet['id'],'method':'meet'},'POST')[0]==403
        # meet -> reject -> relisted -> new meetup -> dual confirmation
        code,e=req(sara,'/api/pickups',{'found_id':wallet['id'],'method':'meet'},'POST');assert code==201,(code,e)
        request_id=e['request_id']
        code,cards=req(guest,'/api/items');assert wallet['id'] not in [x['id'] for x in cards['items']]
        code,staff_entries=req(staff,'/api/pickups');assert request_id not in [x['id'] for x in staff_entries['requests']]
        code,e=req(daniel,f'/api/pickups/{request_id}/reject',{},'POST');assert code==200,(code,e)
        code,cards=req(guest,'/api/items');assert wallet['id'] in [x['id'] for x in cards['items']]
        code,e=req(sara,'/api/pickups',{'found_id':wallet['id'],'method':'meet'},'POST');assert code==201,(code,e)
        request_id=e['request_id']
        code,d=req(sara,'/api/pickups'); assert next(x for x in d['requests'] if x['id']==request_id)['finder_phone'] is None
        assert req(sara,f'/api/pickups/{request_id}/accept',{},'POST')[0]==403
        assert req(daniel,f'/api/pickups/{request_id}/accept',{},'POST')[0]==200
        code,d=req(sara,'/api/pickups'); assert next(x for x in d['requests'] if x['id']==request_id)['finder_phone']=='0112345678'
        assert req(daniel,f'/api/pickups/{request_id}/finder-confirm',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{request_id}/owner-confirm',{},'POST')[0]==200
        code,d=req(sara,'/api/pickups');assert next(x for x in d['requests'] if x['id']==request_id)['status']=='completed'
        # wrong answer -> still shown; correct -> finder -> counter staff -> done
        code,e=req(sara,'/api/pickups',{'found_id':earbud['id'],'method':'counter','answer':'red'},'POST');assert code==403,(code,e)
        assert earbud['id'] in [x['id'] for x in req(guest,'/api/items')[1]['items']]
        code,e=req(sara,'/api/pickups',{'found_id':earbud['id'],'method':'counter','answer':'Blue'},'POST');assert code==201,(code,e)
        counter_id=e['request_id']
        assert req(sara,f'/api/pickups/{counter_id}/submit-counter',{},'POST')[0]==403
        assert req(daniel,f'/api/pickups/{counter_id}/submit-counter',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{counter_id}/receive-counter',{},'POST')[0]==403
        assert req(staff,f'/api/pickups/{counter_id}/receive-counter',{},'POST')[0]==200
        assert req(staff,f'/api/pickups/{counter_id}/release-counter',{},'POST')[0]==200
        assert next(x for x in req(staff,'/api/pickups')[1]['requests'] if x['id']==counter_id)['status']=='completed'
        # Counter can reject an unverified claimant while retaining physical custody.
        code,e=req(sara,'/api/pickups',{'found_id':bag['id'],'method':'counter','answer':'Green'},'POST');assert code==201,(code,e)
        bag_id=e['request_id']
        assert req(daniel,f'/api/pickups/{bag_id}/submit-counter',{},'POST')[0]==200
        assert req(staff,f'/api/pickups/{bag_id}/receive-counter',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{bag_id}/reject-counter',{},'POST')[0]==403
        assert req(staff,f'/api/pickups/{bag_id}/reject-counter',{},'POST')[0]==200
        available=req(guest,'/api/items')[1]['items']
        assert next(x for x in available if x['id']==bag['id'])['custody']=='counter'
        assert req(sara,'/api/pickups',{'found_id':bag['id'],'method':'meet'},'POST')[0]==409
        code,e=req(sara,'/api/pickups',{'found_id':bag['id'],'method':'counter','answer':'Green'},'POST')
        assert code==201,(code,e)
        held_id=e['request_id']
        assert next(x for x in req(staff,'/api/pickups')[1]['requests'] if x['id']==held_id)['status']=='counter_ready'
        assert req(staff,f'/api/pickups/{held_id}/release-counter',{},'POST')[0]==200
        # Daniel may claim a FOUND item posted by Sara.
        assert req(daniel,'/api/pickups',{'found_id':keys['id'],'method':'meet'},'POST')[0]==201
        # reject legacy lost item creation via multipart endpoint, despite tampered client
        boundary='----V6test'
        form=(f'--{boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\nlost\r\n--{boundary}--\r\n').encode()
        request=urllib.request.Request(root+'/api/items',form,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-CSRF-Token':sara.csrf},method='POST')
        try: sara.open(request,timeout=5);raise AssertionError('Lost report was accepted')
        except urllib.error.HTTPError as e:assert e.code==400,e.code
        # Wrong password should be refused.
        assert req(guest,'/api/login',{'email':'sara@campus.test','password':'WrongPass12'},'POST')[0]==401
        print('PASS: Found-only feed; staff isolation; own-item block; meetup rejection/relisting; private contact; dual return; security question; staff counter receipt/rejection/reclaim/release; Lost report blocked; incorrect login.')
    finally:
        proc.terminate()
        try:proc.communicate(timeout=4)
        except:proc.kill()
