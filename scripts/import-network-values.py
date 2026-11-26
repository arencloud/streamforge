#!/usr/bin/env python3
"""Import selected Vault network fields into ignored local values; never print them."""
import argparse
import ipaddress
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE_NETWORKS = tuple(ipaddress.ip_network(n) for n in (
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"))


def parse_cidrs(raw):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = raw
    if isinstance(value, str):
        value = re.split(r"[,\s]+", value.strip())
    if not isinstance(value, list) or not value:
        raise ValueError("CIDRs must be a non-empty JSON array or comma/newline-separated list")
    networks = []
    for item in value:
        if not isinstance(item, str) or "/" not in item:
            raise ValueError("Each destination must include an explicit CIDR prefix")
        try:
            network = ipaddress.ip_network(item.strip(), strict=True)
        except ValueError:
            raise ValueError("Invalid CIDR or host bits set; use a canonical network or host prefix") from None
        if network.prefixlen == 0 or network.is_loopback or network.is_link_local or network.is_multicast or network.is_unspecified:
            raise ValueError("Unrestricted or non-destination network range is not permitted")
        if any(network.version == example.version and network.overlaps(example) for example in EXAMPLE_NETWORKS):
            raise ValueError("Replace documentation-only destination ranges")
        if str(network) not in networks:
            networks.append(str(network))
    return networks


def read_field(mount, path, field):
    # The CLI outputs only this field. Do not request/print the complete KV entry.
    result = subprocess.run(
        ["vault", "kv", "get", "-mount=" + mount, "-field=" + field, path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"Cannot read {field}; check local Vault authentication, policy and field presence")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--values", type=pathlib.Path, default=ROOT / ".local/values.yaml")
    parser.add_argument("--mount", default="secret", help="Vault KV mount name")
    args = parser.parse_args()
    path = args.values.resolve()
    if not path.is_relative_to(ROOT / ".local") or not path.is_file():
        raise ValueError("Use an existing values file inside this repository's ignored .local directory")
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=ROOT, capture_output=True).returncode == 0
    ignored = subprocess.run(["git", "check-ignore", "-q", str(path)], cwd=ROOT).returncode == 0
    if tracked or not ignored:
        raise ValueError("Refusing to write network inventory into a tracked or unignored file")
    if not shutil.which("vault"):
        raise RuntimeError("Install the Vault CLI and authenticate locally before importing")
    values = yaml.safe_load(path.read_text())
    if not isinstance(values, dict):
        raise ValueError("Expected a Helm values mapping")
    prefix = values.get("vaultPrefix", "streamforge")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", prefix) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]*", args.mount):
        raise ValueError("Invalid Vault mount or prefix")
    # Collect and validate every field before modifying the destination file.
    pg = parse_cidrs(read_field(args.mount, prefix + "/postgres", "PG_EGRESS_CIDRS"))
    raw_port = read_field(args.mount, prefix + "/postgres", "PG_PORT")
    if not re.fullmatch(r"[1-9][0-9]{0,4}", raw_port) or int(raw_port) > 65535:
        raise ValueError("PG_PORT must be an integer between 1 and 65535")
    s3 = {sink: parse_cidrs(read_field(args.mount, prefix + "/s3/" + sink, "S3_EGRESS_CIDRS"))
          for sink in ("aiven", "camel", "camel-connect")}
    network = values.setdefault("network", {})
    network.update(postgresCidrs=pg, postgresPort=int(raw_port), s3Cidrs=s3)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".network-", delete=False) as stream:
            temporary = stream.name
            os.chmod(temporary, 0o600)
            yaml.safe_dump(values, stream, sort_keys=False)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    print("Imported PostgreSQL CIDRs/port and three per-sink S3 CIDR lists into ignored local values.")
    print("Review privately and commit to private configuration Git before Argo CD sync. No cluster changes made.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, yaml.YAMLError):
        # Avoid echoing command output, inventory, YAML snippets or secret data.
        print("Network import failed. Verify the Vault CLI/session, field formats, and an ignored .local values file. Destination was not updated.", file=sys.stderr)
        sys.exit(1)
