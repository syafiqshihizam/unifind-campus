import os, sys, tempfile, subprocess, time, http.cookiejar, urllib.request, urllib.error, json, uuid
from pathlib import Path
base=Path(__file__).resolve().parents[1]
dir=tempfile.TemporaryDirectory()
env=os.environ.copy();env['CAMPUSBACK_DB']=str(Path(dir.name)/'state.db');env['CAMPUSBACK_UPLOADS']=str(Path(dir.name)/'uploads');env['PORT']='18736'
seed=subprocess.run([sys.executable,'seed_demo.py'],cwd=base,env=env,capture_output=True,text=True)
print('seed',seed.returncode,seed.stdout[:120],seed.stderr[:300]);assert seed.returncode==0
proc=subprocess.Popen([sys.executable,'server.py'],cwd=base,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
baseurl='http://127.0.0.1:18736'
def client():
    c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    c.csrf=None
    return c
def req(c,path,body=None,method='GET'):
    headers={}
    if method=='POST':
        headers['Content-Type']='application/json'
        if c.csrf:headers['X-CSRF-Token']=c.csrf
    data=None if method=='GET' else json.dumps(body or {}).encode()
    r=urllib.request.Request(baseurl+path,data,headers=headers,method=method)
    try:
        with c.open(r,timeout=4) as response:
            raw=response.read(); return response.status, json.loads(raw)
    except urllib.error.HTTPError as error:
        return error.code,json.loads(error.read())
def login(c,email,password='Demo1234!'):
    code,dat=req(c,'/api/login',{'email':email,'password':password},'POST');assert code==200,(code,dat)
    code,s=req(c,'/api/session');c.csrf=s['csrf_token'];assert s['authenticated'];return s
try:
    for i in range(30):
        try:
            code,_=req(client(),'/api/items');break
        except Exception:time.sleep(.1)
    assert code==200
    sara,daniel,staff=client(),client(),client()
    code,wrong=req(sara,'/api/login',{'email':'sara@campus.test','password':'WRONGPASS'},'POST')
    assert code==401 and 'incorrect' in wrong['error'].lower(),(code,wrong)
    login(sara,'sara@campus.test');login(daniel,'daniel@campus.test');login(staff,'counter@campus.test')
    code,items=req(sara,'/api/items');assert code==200 and len(items['items'])==3,items
    assert all(x['kind']=='found' for x in items['items'])
    wallet=next(i for i in items['items'] if i['name']=='Black wallet')
    earbud=next(i for i in items['items'] if 'Earbuds' in i['name'])
    keys=next(i for i in items['items'] if 'Keys' in i['name'])
    code,info=req(sara,f"/api/items/{wallet['id']}/claim-info");assert code==200 and info['question']=='How many cards are inside?',(code,info)
    code,wrong=req(sara,'/api/direct-claims',{'found_id':wallet['id'],'answer':'nope'},'POST');assert code==403 and 'incorrect' in wrong['error'].lower(),wrong
    code,correct=req(sara,'/api/direct-claims',{'found_id':wallet['id'],'answer':'3'},'POST');assert code==201, (code,correct)
    code,claims=req(sara,'/api/claims');assert code==200,(code,claims)
    direct=next(c for c in claims['claims'] if c['source']=='direct')
    assert direct['role']=='owner' and direct['status']=='verified'
    code,sitems=req(sara,'/api/items');assert wallet['id'] not in [x['id'] for x in sitems['items']]
    code,deny=req(daniel,f"/api/direct-claims/{direct['id']}/owner-confirm",{},'POST');assert code==403,(code,deny)
    code,cf1=req(sara,f"/api/direct-claims/{direct['id']}/owner-confirm",{},'POST');assert code==200 and cf1['status']=='verified',cf1
    code,cf2=req(daniel,f"/api/direct-claims/{direct['id']}/finder-confirm",{},'POST');assert code==200 and cf2['status']=='returned',cf2
    code,done=req(sara,'/api/claims');assert next(c for c in done['claims'] if c['source']=='direct')['status']=='returned'
    code,cinfo=req(sara,f"/api/items/{earbud['id']}/claim-info");assert code==200 and cinfo['at_counter'],(code,cinfo)
    code,cwrong=req(sara,f"/api/counter/{cinfo['counter_id']}/claim",{'answer':'Samsung'},'POST');assert code==403,(code,cwrong)
    code,ccorrect=req(sara,f"/api/counter/{cinfo['counter_id']}/claim",{'answer':'AirPods'},'POST');assert code==201,(code,ccorrect)
    code,ct=req(sara,'/api/counter');assert any(s['status']=='claim_pending' for s in ct['submissions'])
    code,cdenied=req(sara,f"/api/counter/{cinfo['counter_id']}/release",{},'POST');assert code==403
    code,cstaff=req(staff,f"/api/counter/{cinfo['counter_id']}/release",{},'POST');assert code==200,(code,cstaff)
    code,claimed=req(sara,'/api/counter');assert any(s['status']=='claimed' for s in claimed['submissions'])
    code,cpend=req(sara,f"/api/items/{keys['id']}/claim-info");assert code==409,(code,cpend)
    code,stafflist=req(staff,'/api/counter');pending=next(s for s in stafflist['submissions'] if s['found_id']==keys['id'])
    code,receive=req(staff,f"/api/counter/{pending['id']}/receive",{},'POST');assert code==200,receive
    code,kinfo=req(sara,f"/api/items/{keys['id']}/claim-info");assert code==200 and kinfo['at_counter']
    code,ownfail=req(daniel,f"/api/items/{keys['id']}/claim-info");assert code==403
    print('PASSED: found-only, login error, detail question, wrong answer, direct claim, redirect data, two-party return, counter claim, staff-only receipt and release')
finally:
    proc.terminate()
    try:proc.communicate(timeout=4)
    except:proc.kill()
    dir.cleanup()
