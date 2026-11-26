#!/usr/bin/env python3
"""Compare locally downloaded synthetic showcase objects without printing their contents."""
import argparse
import collections
import hashlib
import json
import pathlib


def events(path):
    found = collections.Counter()
    signatures = set()
    for file in pathlib.Path(path).rglob("*"):
        if file.suffix not in (".json", ".jsonl"):
            continue
        for line in file.read_text().splitlines():
            record = json.loads(line)
            value = record.get("value")
            if isinstance(value, str):
                value = json.loads(value)
            if not isinstance(value, dict):
                continue
            row = value.get("after") or value.get("before") or {}
            if row.get("id") not in (910001, 910002):
                continue
            found[(row["id"], value.get("op"))] += 1
            signatures.add(hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
    expected = {(910001, "c"), (910002, "c"), (910001, "u"), (910002, "d")}
    if not expected.issubset(found):
        raise SystemExit("Missing expected CDC operations; wait for flush or inspect connector health")
    return found, signatures


parser = argparse.ArgumentParser()
parser.add_argument("directories", nargs="+", help="One output directory per sink")
args = parser.parse_args()
results = [events(path) for path in args.directories]
if any(sigs != results[0][1] for _, sigs in results[1:]):
    raise SystemExit("Sink payload sets differ")
for counts, sigs in results:
    print(f"Verified {sum(counts.values())} delivered records, {len(sigs)} distinct CDC envelopes")
