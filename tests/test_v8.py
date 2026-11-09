"""V7 integration tests: students + finder decline, alternative collection, owner-only return, categorized counter desk."""
import os,sys,tempfile,subprocess,time,urllib.request,urllib.error,http.cookiejar,json
from pathlib import Path
base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    env=dict(os.environ,CAMPUSBACK_DB=str(Path(td)/'state.db'),CAMPUSBACK_UPLOADS=str(Path(td)/'uploads'),PORT='18767')
    seed=subprocess.run([sys.executable,'seed_demo.py'],cwd=base,env=env,capture_output=True,text=True)
    assert seed.returncode==0,(seed.stdout,seed.stderr)
    proc=subprocess.Popen([sys.executable,'server.py'],cwd=base,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    root='http://127.0.0.1:18767'
    def client():
        c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));c.csrf=None
        return c
    def req(c,path,data=None,method='GET'):
        headers={};raw=None
        if method=='POST':
            raw=json.dumps(data or {}).encode();headers['Content-Type']='application/json'
            if c.csrf:headers['X-CSRF-Token']=c.csrf
        r=urllib.request.Request(root+path,raw,headers=headers,method=method)
        try:
            with c.open(r,timeout=5) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as err:return err.code,json.loads(err.read())
    def login(c,email):
        z=req(c,'/api/login',{'email':email,'password':'Demo1234!'},'POST')
        assert z[0]==200,z
        s=req(c,'/api/session')[1]
        c.csrf=s['csrf_token'];return s
    try:
        for _ in range(40):
            try:
                if req(client(),'/api/items')[0]==200:break
            except Exception:time.sleep(.15)
        else:raise AssertionError('Server not started')
        sara,daniel,staff,guest=(client() for _ in range(4))
        assert login(sara,'sara@campus.test')['user']['is_staff'] is False
        assert login(daniel,'daniel@campus.test')['user']['is_staff'] is False
        assert login(staff,'counter@campus.test')['user']['is_staff'] is True
        code,data=req(guest,'/api/items');assert code==200 and len(data['items'])==4,data
        assert all(i['kind']=='found' for i in data['items'])
        wallet=next(i for i in data['items'] if 'Wallet' in i['name'])
        earbuds=next(i for i in data['items'] if 'Earbuds' in i['name'])
        keys=next(i for i in data['items'] if 'Keys' in i['name'])
        bag=next(i for i in data['items'] if 'Backpack' in i['name'])
        # Sara (owner) claims Daniel's wallet, finder declines due to absence.
        code,z=req(sara,'/api/pickups',{'found_id':wallet['id'],'method':'meet'},'POST');assert code==201,z
        rid=z['request_id']
        assert req(sara,f'/api/pickups/{rid}/reject',{'reason':'not_on_campus'},'POST')[0]==403
        assert req(daniel,f'/api/pickups/{rid}/reject',{'reason':'not_on_campus'},'POST')[0]==200
        dr=next(r for r in req(sara,'/api/pickups')[1]['requests'] if r['id']==rid)
        assert dr['status']=='meet_declined' and 'not currently on campus' in dr['rejection_note'],dr
        assert req(sara,f'/api/pickups/{rid}/switch-counter',{'answer':'wrong'},'POST')[0]==403
        assert req(sara,f'/api/pickups/{rid}/switch-counter',{'answer':'3'},'POST')[0]==200
        dr=next(r for r in req(sara,'/api/pickups')[1]['requests'] if r['id']==rid)
        assert dr['method']=='counter' and dr['status']=='counter_waiting_finder'
        assert req(daniel,f'/api/pickups/{rid}/submit-counter',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{rid}/receive-counter',{},'POST')[0]==403
        assert req(staff,f'/api/pickups/{rid}/receive-counter',{},'POST')[0]==200
        assert req(staff,f'/api/pickups/{rid}/release-counter',{},'POST')[0]==200
        # Meetup owner-only completion, finder cannot complete it.
        code,z=req(sara,'/api/pickups',{'found_id':earbuds['id'],'method':'meet'},'POST');assert code==201,z
        rid=z['request_id']
        assert req(daniel,f'/api/pickups/{rid}/accept',{},'POST')[0]==200
        assert req(daniel,f'/api/pickups/{rid}/owner-confirm',{},'POST')[0]==403
        assert req(daniel,f'/api/pickups/{rid}/finder-confirm',{},'POST')[0] in (404,410) # old button removed
        assert req(sara,f'/api/pickups/{rid}/owner-confirm',{},'POST')[0]==200
        assert next(r for r in req(sara,'/api/pickups')[1]['requests'] if r['id']==rid)['status']=='completed'
        # Meet is wrong item: relist with owner button
        code,z=req(sara,'/api/pickups',{'found_id':bag['id'],'method':'meet'},'POST');assert code==201,z
        rid=z['request_id'];assert req(daniel,f'/api/pickups/{rid}/accept',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{rid}/not-my-item',{},'POST')[0]==200
        assert bag['id'] in [i['id'] for i in req(guest,'/api/items')[1]['items']]
        # Finder declines schedule: owner waits, finder accepts later
        code,z=req(daniel,'/api/pickups',{'found_id':keys['id'],'method':'meet'},'POST');assert code==201,z
        rid=z['request_id']
        assert req(sara,f'/api/pickups/{rid}/reject',{'reason':'schedule_conflict'},'POST')[0]==200
        assert req(daniel,f'/api/pickups/{rid}/wait-finder',{},'POST')[0]==200
        assert req(sara,f'/api/pickups/{rid}/accept',{},'POST')[0]==200
        assert req(daniel,f'/api/pickups/{rid}/not-my-item',{},'POST')[0]==200
        # Invalid reason fails, and finder can reject wrong claimant and restore item
        code,z=req(sara,'/api/pickups',{'found_id':bag['id'],'method':'meet'},'POST');assert code==201,z
        rid=z['request_id'];assert req(daniel,f'/api/pickups/{rid}/reject',{},'POST')[0]==400
        assert req(daniel,f'/api/pickups/{rid}/reject',{'reason':'not_owner'},'POST')[0]==200
        assert bag['id'] in [i['id'] for i in req(guest,'/api/items')[1]['items']]
        assert req(staff,'/api/pickups',{'found_id':bag['id'],'method':'meet'},'POST')[0]==403
        assert req(guest,'/api/login',{'email':'counter@campus.test','password':'NopeNope23'},'POST')[0]==401
        print('PASS V8: 4 found items, 2 student logins + staff, founder decline/reasons, counter switch with failed and correct security, staff receipt/collection permissions, single owner confirmation, owner not-my-item reopens community, wait-for-finder, rejection/relisting, invalid reason and login rejection.')
    finally:
        proc.terminate()
        try:proc.communicate(timeout=5)
        except:proc.kill()
