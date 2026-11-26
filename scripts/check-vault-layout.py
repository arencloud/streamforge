#!/usr/bin/env python3
"""Check the field-only Vault inventory against every chart's ESO references."""
from pathlib import Path
import subprocess
import yaml

root = Path(__file__).resolve().parents[1]
inventory = yaml.safe_load((root / 'docs/examples/vault-layout.yaml').read_text())
assert all(value is None for fields in inventory.values() for value in fields.values()), 'Vault inventory must contain field names only'
used = set()
for chart, extra in [('streamforge', ['--set', 'dashboard.enabled=true']), ('streamforge-edge', [])]:
    rendered = subprocess.check_output(['helm', 'template', chart, str(root / 'charts' / chart), '-n', 'streamforge', *extra], text=True)
    for resource in yaml.safe_load_all(rendered):
        if not resource or resource['kind'] != 'ExternalSecret':
            continue
        for field in resource['spec'].get('data', []):
            ref = field['remoteRef']
            name = 'secret/' + ref['key']
            assert name in inventory and ref['property'] in inventory[name], f'Missing Vault inventory field: {name}/{ref["property"]}'
            used.add((name, ref['property']))
metadata = {('secret/streamforge/postgres', 'PG_EGRESS_CIDRS')}
metadata.update(('secret/streamforge/s3/' + sink, 'S3_EGRESS_CIDRS') for sink in ('aiven', 'camel', 'camel-connect'))
actual = {(name, field) for name, fields in inventory.items() for field in fields}
assert actual == used | metadata, 'Inventory contains undocumented or unused fields'
print(f'Vault inventory passed: {len(used)} consumed fields and {len(metadata)} provisioning metadata fields; no values.')
