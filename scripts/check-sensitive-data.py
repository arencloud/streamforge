#!/usr/bin/env python3
"""Scan Git publication candidates and optionally fetched history; redact findings."""
import argparse
import pathlib
import shutil
import subprocess
import tempfile

root = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--history', action='store_true', help='Also scan all locally available Git refs')
a = p.parse_args()
binary = shutil.which('gitleaks')
if not binary:
    raise SystemExit('Gitleaks is required; see docs/publication-safety.md for the pinned version.')
paths = sorted(set(filter(None, subprocess.check_output(
    ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=root
).decode().split('\0'))))
flags = ['--config=' + str(root / '.gitleaks.toml'), '--redact=100', '--no-banner', '--no-color', '--ignore-gitleaks-allow', '--max-decode-depth=2']
result = subprocess.run(['python3', str(root / 'scripts/scan-secrets.py')], cwd=root).returncode
# Export only publication candidates: never scan ignored local credentials or build output.
with tempfile.TemporaryDirectory(prefix='streamforge-publication-') as temp:
    for name in paths:
        source = root / name
        if source.is_symlink():
            raise SystemExit('Symlinks are not allowed in publication candidates.')
        if not source.is_file():
            continue
        destination = pathlib.Path(temp) / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    result |= subprocess.run([binary, 'dir', *flags, temp], cwd=temp).returncode
if a.history:
    commits = subprocess.check_output(['git', 'rev-list', '--count', '--all'], cwd=root).strip()
    if commits != b'0':
        result |= subprocess.run([binary, 'git', *flags, '--log-opts=--all', str(root)], cwd=root).returncode
    else:
        print('No local commits to scan; current publication candidates were scanned.')
raise SystemExit(result)
