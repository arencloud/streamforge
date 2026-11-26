#!/usr/bin/env python3
"""Small offline guard for common accidental credentials; never prints matched values."""
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parents[1]
paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
patterns = [
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"sha256~[A-Za-z0-9_-]{30,}"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(rb"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{25,}"),
    re.compile(rb"\bhvs\.[A-Za-z0-9_-]{20,}"),
    re.compile(rb"https?://[^\s/:]+:[^\s/@]+@"),
]
failed = False
for path in sorted(set(paths)):
    if not path or not (root / path).is_file():
        continue
    data = (root / path).read_bytes()
    if any(p.search(data) for p in patterns):
        print(f"Possible credential in {path}; inspect locally", file=sys.stderr)
        failed = True
sys.exit(1 if failed else 0)
