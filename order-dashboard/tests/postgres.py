import subprocess,time,json
pg='streamforge-dashboard-pg-test'; app='streamforge-dashboard-db-test'
def run(args,**kw):return subprocess.run(args,check=True,**kw)
def api(path,method='GET',body=None):
    args=['docker','exec',app,'curl','-sS','-w','\n%{http_code}','-X',method,'-H','Content-Type: application/json','-H','X-Streamforge-Action: orders']
    if body is not None:args+=['-d',json.dumps(body)]
    r=run(args+['http://127.0.0.1:8080'+path],capture_output=True,text=True)
    text,status=r.stdout.rsplit('\n',1);return int(status),json.loads(text)
try:
    run(['docker','run','-d','--name',pg,'--network','none','-e','POSTGRES_HOST_AUTH_METHOD=trust','postgres:18.6','-c','listen_addresses=localhost'],stdout=subprocess.DEVNULL)
    for _ in range(60):
        r=subprocess.run(['docker','exec',pg,'psql','-U','postgres','-tAc','SELECT 1'],capture_output=True)
        logs=subprocess.run(['docker','logs',pg],capture_output=True,text=True)
        if r.returncode==0 and 'init process complete' in logs.stdout:break
        time.sleep(.5)
    else:raise RuntimeError('Fixture PostgreSQL not ready')
    run(['docker','exec',pg,'psql','-U','postgres','-v','ON_ERROR_STOP=1','-c','CREATE TABLE public.orders (id bigint PRIMARY KEY, customer_name text NOT NULL, amount numeric(12,2) NOT NULL, status text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())'],stdout=subprocess.DEVNULL)
    run(['docker','run','-d','--name',app,'--network','container:'+pg,'--read-only','--tmpfs','/tmp:rw,size=128m','--user','100123:0','-e','PG_HOST=localhost','-e','PG_DATABASE=postgres','-e','PG_APP_USERNAME=postgres','-e','JAVA_TOOL_OPTIONS=-Dquarkus.datasource.jdbc.additional-jdbc-properties.sslmode=disable','streamforge/order-dashboard:test'],stdout=subprocess.DEVNULL)
    for _ in range(50):
        try:
            status,d=api('/api/orders')
            if status==200: assert not d['preview'];break
        except Exception:pass
        time.sleep(.5)
    else:raise RuntimeError('App did not connect to fixture PostgreSQL')
    status,o=api('/api/orders','POST',{'id':912340,'customerName':'Isolated SQL fixture','amount':12.50});assert status==201,(status,o)
    status,_=api('/api/orders','POST',{'id':912340,'customerName':'Duplicate','amount':12.50});assert status==409
    status,_=api('/api/orders/912340/status','PATCH',{'status':'shipped','expectedUpdatedAt':o['updatedAt']});assert status==400
    status,n=api('/api/orders/912340/status','PATCH',{'status':'paid','expectedUpdatedAt':o['updatedAt']});assert status==200,(status,n)
    status,_=api('/api/orders/912340/status','PATCH',{'status':'cancelled','expectedUpdatedAt':o['updatedAt']});assert status==409
    status,c=api('/api/orders/912340/status','PATCH',{'status':'cancelled','expectedUpdatedAt':n['updatedAt']});assert status==200
    r=run(['docker','exec',pg,'psql','-U','postgres','-tAc',"SELECT status || ':' || amount FROM public.orders WHERE id=912340"],capture_output=True,text=True)
    assert r.stdout.strip()=='cancelled:12.50'
    status,current=api('/api/orders','POST',{'id':912341,'customerName':'Lifecycle fixture','amount':150});assert status==201
    for next_status in ('paid','shipped','completed'):
        status,current=api('/api/orders/912341/status','PATCH',{'status':next_status,'expectedUpdatedAt':current['updatedAt']});assert status==200,(status,current)
        assert current['status']==next_status
        status,listing=api('/api/orders');assert status==200
        saved=next(v['order'] for v in listing['orders'] if v['order']['id']==912341)
        assert saved==current,(saved,current)
    r=run(['docker','exec',pg,'psql','-U','postgres','-tAc',"SELECT status FROM public.orders WHERE id=912341"],capture_output=True,text=True)
    assert r.stdout.strip()=='completed'
    print('Real PostgreSQL fixture passed: full paid/shipped/completed lifecycle plus inserts, duplicates, transition rejection, optimistic locking, persisted update.')
finally:
    for name in (app,pg):subprocess.run(['docker','rm','-fv',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
