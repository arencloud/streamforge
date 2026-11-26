#!/usr/bin/env python3
"""Check publication candidates without printing matched infrastructure details."""
import argparse
import ipaddress
import pathlib
import re
import subprocess
import sys
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--deny-file", type=pathlib.Path, help="Ignored local file of additional private terms, one per line")
parser.add_argument("--history", action="store_true", help="Also inspect file versions reachable from local Git refs")
args = parser.parse_args()
terms = []
if args.deny_file:
    terms = [s.strip().lower() for s in args.deny_file.read_text().splitlines() if s.strip() and not s.startswith("#")]
paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
private_networks = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")]
failures = []
def inspect(name, data):
    if name.startswith((".local/", "environments/private/", ".idea/", ".vscode/", ".kube/", ".aws/", ".docker/", ".argocd/", ".secrets/")):
        failures.append((name, "private directory is tracked"))
        return
    if name.startswith("environments/") and not name.startswith("environments/example/"):
        failures.append((name, "public environments must contain examples only"))
    basename = pathlib.PurePosixPath(name).name
    if (basename.startswith(".env") and basename != ".env.example") or re.search(r"(?:\.(?:pem|key|p12|pfx|jks|kubeconfig|tfstate)$|^kubeconfig|^\.vault-token$|^\.netrc$|^\.pgpass$|^\.s3cfg$)", basename):
        failures.append((name, "credential/configuration file is tracked"))
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    if any(term in content.lower() or term in name.lower() for term in terms):
        failures.append((name, "matches a locally supplied private term"))
    if re.search(r"/(?:Users|home)/[A-Za-z0-9_.-]+/", content):
        failures.append((name, "personal filesystem path"))
    ip_content = content
    for candidate in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", ip_content):
        # Permit only this guard's three network-base constants, not its other content.
        if name == "scripts/check-public.py" and candidate in ("10.0.0.0", "172.16.0.0", "192.168.0.0"):
            continue
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if any(address in network for network in private_networks):
            failures.append((name, "private IPv4 address"))
            break
    for candidate in re.findall(r"\b(?:fc|fd)[0-9a-f]{2}:[0-9a-f:]+", ip_content, re.I):
        # Standard Istio probe SNAT address, not a deployment-specific allocation.
        if candidate.lower() != "fd16:9254:7127:1337:ffff:ffff:ffff:ffff":
            failures.append((name, "private IPv6 address"))
            break
    for url in re.findall(r"https?://[^\s\"'<>`){}]+", content):
        try:
            host = urlparse(url).hostname or ""
        except ValueError:
            continue  # Regex/string templates in source code need not be concrete URLs.
        if re.match(r"^(?:api|argocd|vault|postgres|pgsql|s3|auth)\.", host):
            if not host.endswith((".example.invalid", ".example.com", ".test", ".localhost")):
                failures.append((name, "possible deployment endpoint"))

for name in sorted(set(paths)):
    path = ROOT / name
    if not name:
        continue
    if path.is_symlink():
        failures.append((name, "symlink is not allowed in publication candidates"))
    elif path.is_file():
        inspect(name, path.read_bytes())
if args.history:
    # Unique blobs avoid rescanning unchanged content across many commits.
    refs = subprocess.check_output(["git", "for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes", "refs/tags"], cwd=ROOT).decode().splitlines()
    if subprocess.run(["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=ROOT, capture_output=True).returncode == 0:
        refs.append("HEAD")
    # Tool checkpoint refs are not branch/tag history and are never published by a normal push.
    objects = subprocess.check_output(["git", "rev-list", "--objects", *refs], cwd=ROOT).decode() if refs else ""
    for entry in objects.splitlines():
        oid, separator, name = entry.partition(" ")
        if not separator:
            continue
        kind = subprocess.check_output(["git", "cat-file", "-t", oid], cwd=ROOT).strip()
        if kind == b"blob":
            inspect(name, subprocess.check_output(["git", "cat-file", "blob", oid], cwd=ROOT))
for name, reason in sorted(set(failures)):
    print(f"Publication check: {name}: {reason}", file=sys.stderr)
if failures:
    sys.exit(1)
print("Public-file checks passed (publication candidates and requested history).")
