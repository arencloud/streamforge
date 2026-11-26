#!/usr/bin/env python3
"""Validate RHCL edge security and dedicated identity manifests without secret access."""
import argparse,pathlib,subprocess,re
import yaml
p=argparse.ArgumentParser();p.add_argument('-f',action='append',default=[]);p.add_argument('--production',action='store_true');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
cmd=['helm','template','streamforge-edge',str(root/'charts/streamforge-edge'),'-n','streamforge']
for f in a.f:cmd+=['-f',f]
docs=[d for d in yaml.safe_load_all(subprocess.check_output(cmd,text=True)) if d]
assert not any(d['kind']=='Secret' for d in docs)
wasm=next(d for d in docs if d['kind']=='WasmPlugin')['spec']
assert wasm['failStrategy']=='FAIL_CLOSE' and 'SecRuleEngine On' in wasm['pluginConfig']['directives_map']['default']
directives=wasm['pluginConfig']['directives_map']['default']
patch_rule=next(x for x in directives if 'id:10010,' in x)
assert 'REQUEST_HEADERS:Host' in patch_rule and '^/api/orders/[0-9]+/status$' in patch_rule
assert 'REQUEST_METHOD "@streq PATCH"' in patch_rule and 'tx.allowed_methods=GET HEAD POST OPTIONS PATCH' in patch_rule
assert directives.index(patch_rule)<directives.index('Include @owasp_crs/*.conf')
assert 'SecRuleRemove' not in patch_rule and 'ruleEngine' not in patch_rule
assert any(d['kind']=='TLSPolicy' and d['spec']['issuerRef']['kind']=='ClusterIssuer' for d in docs)
realm=next(d for d in docs if d['kind']=='KeycloakRealmImport')['spec']['realm']
client=realm['clients'][0]
assert client['publicClient'] and client['attributes']['pkce.code.challenge.method']=='S256'
assert not client['directAccessGrantsEnabled'] and not client['implicitFlowEnabled']
assert 'secret' not in client and all(u['credentials'][0]['value'].startswith('${') for u in realm['users'])
for d in docs:
 if d['kind']=='HTTPRoute' and d['metadata']['name']=='streamforge-web':
  paths={m['path']['value'] for r in d['spec']['rules'] for m in r['matches']}
  assert not any(x.startswith(('/api','/q/','/internal')) for x in paths)
  assert all(m['path']['type']=='Exact' and m['method']=='GET' for r in d['spec']['rules'] for m in r['matches'])
 if d['kind']=='AuthPolicy' and d['metadata']['name']=='streamforge-api':
  jwt=d['spec']['rules']['authentication']['keycloak']['jwt']
  assert jwt['issuer'].startswith('https://') and jwt['audiences']
  assert 'streamforge-operator' in d['spec']['rules']['authorization']['roles']['opa']['rego']
 if d['kind']=='RateLimitPolicy':
  assert all(l['rates'][0]['limit']>0 for l in d['spec']['limits'].values())
  source=d['spec']['limits'].get('source',{})
  assert all('"' not in c['expression'] for l in d['spec']['limits'].values() for c in l.get('counters',[])), 'Use single-quoted CEL literals: installed operator embeds expression names in double-quoted Limitador keys'
  assert 'lastIndexOf' in source['counters'][0]['expression'], 'Source limits must aggregate across ephemeral connection ports'
if a.production:
 assert 'example.invalid' not in yaml.safe_dump(docs)
 assert re.fullmatch(r'oci://[^ ]+@sha256:[a-f0-9]{64}',wasm['url'])
print(f'Edge: {len(docs)} resources validated; JWT, PKCE, WAF, TLS and route separation checked')
