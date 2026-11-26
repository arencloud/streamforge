import subprocess,time,json
for arch in ('amd64','arm64'):
    name='streamforge-dashboard-smoke-'+arch
    try:
        subprocess.run(['docker','run','-d','--name',name,'--platform','linux/'+arch,'--network','none','--read-only','--tmpfs','/tmp:rw,size=128m','--user','100123:0','-e','JAVA_TOOL_OPTIONS=-Dquarkus.profile=preview','streamforge/order-dashboard:test'],check=True,stdout=subprocess.DEVNULL)
        for attempt in range(40):
            r=subprocess.run(['docker','exec',name,'curl','-fsS','http://127.0.0.1:8080/api/orders'],capture_output=True,text=True)
            if r.returncode==0:
                d=json.loads(r.stdout); assert d['preview'] is True and len(d['orders'])==3; break
            time.sleep(.5)
        else: raise RuntimeError('Container did not become ready: '+arch)
        print(arch+': arbitrary UID, read-only filesystem, preview API passed')
    finally:
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
