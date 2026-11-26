#!/usr/bin/env python3
"""Probe deployed edge protections without credentials or order mutations."""
import argparse
import ssl
import urllib.error
import urllib.parse
import urllib.request

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--url', required=True, help='Dashboard HTTPS origin')
p.add_argument('--ca-file', help='CA bundle for a private issuer')
a = p.parse_args()
origin = urllib.parse.urlsplit(a.url)
if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('', '/'):
    p.error('--url must be an HTTPS origin without credentials or path')
context = ssl.create_default_context(cafile=a.ca_file)
checks = [
    ('GET', '/health/ready', 200),
    ('GET', '/api/orders', 401),
    # Nonexistent ID and no bearer token: no order is mutated by these probes.
    ('PATCH', '/api/orders/0/status', 401),
    ('PATCH', '/api/orders', 403),
    ('DELETE', '/api/orders/0/status', 403),
    ('GET', '/health/ready?probe=%3Cscript%3Ealert%281%29%3C%2Fscript%3E', 403),
]
for method, path, expected in checks:
    data = b'{"status":"paid","expectedUpdatedAt":"2000-01-01T00:00:00Z"}' if method == 'PATCH' else None
    req = urllib.request.Request(a.url.rstrip('/') + path, data=data, method=method,
        headers={'Content-Type': 'application/json', 'X-Streamforge-Action': 'orders'})
    try:
        with urllib.request.urlopen(req, context=context, timeout=15) as response:
            status = response.status
    except urllib.error.HTTPError as e:
        status = e.code
        e.close()
    if status != expected:
        raise SystemExit(f'FAIL {method} {path}: expected {expected}, received {status}')
    print(f'PASS {method} {path}: {status}')
