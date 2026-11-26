#!/usr/bin/env python3
"""Verify redacted guard failures with synthetic fixtures in an isolated Git repo."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='streamforge-guard-test-') as temp:
    work = Path(temp)
    (work / 'scripts').mkdir()
    for name in ('check-public.py', 'scan-secrets.py', 'check-sensitive-data.py'):
        shutil.copyfile(root / 'scripts' / name, work / 'scripts' / name)
    shutil.copyfile(root / '.gitleaks.toml', work / '.gitleaks.toml')
    subprocess.run(['git', 'init', '-q', '--initial-branch=main'], cwd=work, check=True)
    (work / '.gitignore').write_text('.idea/\n.local/\n')
    sample = work / 'example.txt'
    def check(script, expected, *args, redacted=None):
        r = subprocess.run(['python3', 'scripts/' + script, *args], cwd=work, capture_output=True, text=True)
        assert r.returncode == expected, (script, r.returncode, 'unexpected guard result')
        if redacted:
            assert redacted not in r.stdout + r.stderr, 'A guard printed matched content'
    sample.write_text('\n'.join(['https://api.cluster.example.invalid', '2001:db8::1/128']))
    check('check-public.py', 0)
    sample.write_text('.'.join(('10', '23', '45', '67')))
    check('check-public.py', 1, redacted=sample.read_text())
    sample.write_text('fd' + '12:3456::99')
    check('check-public.py', 1, redacted=sample.read_text())
    sample.write_text('https://' + 'api.private-fixture.net')
    check('check-public.py', 1, redacted=sample.read_text())
    sample.write_text('safe example\n')
    (work / '.idea').mkdir();(work / '.idea/workspace.xml').write_text('<project/>')
    subprocess.run(['git', 'add', '-f', '.idea/workspace.xml'], cwd=work, check=True)
    check('check-public.py', 1)
    subprocess.run(['git', 'rm', '--cached', '-q', '.idea/workspace.xml'], cwd=work, check=True)
    check('check-public.py', 0)
    # Deliberately invalid fixture: never a usable credential or project identity.
    marker = 'sha256' + '~' + 'not-a-real-credential-' * 3
    sample.write_text(marker)
    check('scan-secrets.py', 1, redacted=marker)
    sample.write_text('safe example\n');check('scan-secrets.py', 0)
    # A removed private address still fails the history scan.
    sample.write_text('fd' + '12:3456::99')
    env = dict(os.environ, GIT_AUTHOR_NAME='Publication fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Publication fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    subprocess.run(['git', 'add', '.'], cwd=work, check=True)
    subprocess.run(['git', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Synthetic fixture'], cwd=work, env=env, check=True)
    sample.unlink()
    subprocess.run(['git', 'add', '-u'], cwd=work, check=True)
    subprocess.run(['git', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Remove fixture'], cwd=work, env=env, check=True)
    check('check-public.py', 0)
    check('check-public.py', 1, '--history', redacted='fd' + '12:3456::99')
    if shutil.which('gitleaks'):
        sample.write_text(marker)
        check('check-sensitive-data.py', 1, redacted=marker)
        subprocess.run(['git', 'add', 'example.txt'], cwd=work, check=True)
        subprocess.run(['git', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Invalid token fixture'], cwd=work, env=env, check=True)
        sample.unlink()
        subprocess.run(['git', 'add', '-u'], cwd=work, check=True)
        subprocess.run(['git', '-c', 'commit.gpgsign=false', 'commit', '-qm', 'Remove token fixture'], cwd=work, env=env, check=True)
        check('check-sensitive-data.py', 0)
        check('check-sensitive-data.py', 1, '--history', redacted=marker)
        print('Gitleaks integration passed: current and deleted historical token fixtures fail with redaction.')
print('Publication guards passed: safe examples, private addresses/endpoints, tracked IDE file, redacted credentials, removed history.')
