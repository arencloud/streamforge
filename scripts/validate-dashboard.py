#!/usr/bin/env python3
"""Check optional dashboard access and credential separation on rendered manifests."""
import pathlib
import subprocess
import yaml
from validate import check
root=pathlib.Path(__file__).resolve().parents[1]
cmd=['helm','template','streamforge',str(root/'charts/streamforge'),'-n','streamforge','--set','dashboard.enabled=true']
docs=[d for d in yaml.safe_load_all(subprocess.check_output(cmd,text=True)) if d]
check(docs,'all')
by={(d['kind'],d['metadata']['name']):d for d in docs}
pod=by['Deployment','order-dashboard']['spec']['template']['spec']
assert pod['automountServiceAccountToken'] is False
assert pod['containers'][0]['securityContext']['readOnlyRootFilesystem'] is True
assert not any(d['kind'] in ('Route','Ingress','HTTPRoute') for d in docs)
policy=by['AuthorizationPolicy','dashboard-local-access-only']['spec']
assert policy['selector']=={'matchLabels':{'app':'order-dashboard'}} and policy['action']=='DENY'
for env in pod['containers'][0]['env']:
    if env['name'].startswith('PG_APP_'):
        assert env['valueFrom']['secretKeyRef']['name']=='dashboard-postgres'
for sink in ('aiven','camel','camel-connect'):
    data=by['ExternalSecret','dashboard-s3-'+sink]['spec']['data']
    for item in data:
        if item['secretKey'] in ('access-key-id','secret-access-key'):
            assert '/dashboard/s3/' in item['remoteRef']['key'], 'Must never reuse writer credentials'
for override in ('mode=aiven','mesh.enabled=false','postgres.table=public.customers'):
    result=subprocess.run(cmd+['--set',override],capture_output=True)
    assert result.returncode!=0, 'Unsupported dashboard combination should fail'
print('Dashboard credential separation, local access and invalid-profile checks passed')
