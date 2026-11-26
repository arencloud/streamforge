#!/usr/bin/env bash
set -euo pipefail
# Explicit registration using private environment files. This never syncs workloads.
revision=${1:?Usage: scripts/argocd-create.sh FULL_GIT_COMMIT MODE APPLICATION_YAML PROJECT_YAML VALUES_YAML}
mode=${2:?Choose aiven, camel, camel-connect, both or all}
application_file=${3:?Provide the configured Application from private Git}
project_file=${4:?Provide the configured AppProject from private Git}
values_file=${5:?Provide values matching the pinned private Git commit}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || { echo 'Expected full Git commit SHA' >&2; exit 1; }
case "$mode" in aiven|camel|camel-connect|both|all) ;; *) echo 'Invalid mode' >&2; exit 1 ;; esac
# Run from the public source repository root; do not reinterpret caller file paths.
[[ -f charts/streamforge/Chart.yaml ]] || { echo 'Run from the repository root' >&2; exit 1; }
[[ "$(git rev-parse HEAD)" == "$revision" ]] || { echo 'Check out the exact public release commit' >&2; exit 1; }
[[ -z "$(git status --porcelain -- charts environments gitops connect camel-s3 camel-connect scripts)" ]] || { echo 'Commit the release files before registering the Application' >&2; exit 1; }
tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT
python3 - "$revision" "$mode" "$application_file" "$project_file" > "$tmp_file" <<'PYTHON'
import re, sys, yaml
from urllib.parse import urlparse
revision, mode, app_path, project_path = sys.argv[1:]
with open(app_path) as f:
    app = yaml.safe_load(f)
with open(project_path) as f:
    project = yaml.safe_load(f)
assert app['kind'] == 'Application' and project['kind'] == 'AppProject'
sources = app['spec']['sources']
assert len(sources) == 2, 'Expected public chart and private values sources'
chart, values = sources
assert chart['path'] == 'charts/streamforge' and values['ref'] == 'values'
assert 'path' not in values, 'Private values source must not render unrelated manifests'
chart['targetRevision'] = revision
assert re.fullmatch(r'[0-9a-f]{40}', values['targetRevision']), 'Pin private values to a full commit SHA'
helm = chart['helm']
assert helm['releaseName'] == 'streamforge', 'This helper validates the streamforge release name'
assert helm['valueFiles'] == ['$values/environments/production/values.yaml', '../../environments/example/all.yaml'], 'Review custom value-file layouts separately'
assert not any(k in helm for k in ('values', 'valuesObject', 'fileParameters')), 'Use the reviewed private values file'
assert not any(p['name'] != 'mode' for p in helm.get('parameters', [])), 'Additional Helm overrides are not validated by this helper'
helm['parameters'] = [{'name': 'mode', 'value': mode}]
assert app['spec']['destination']['namespace'] == 'streamforge'
assert app['spec']['project'] == project['metadata']['name']
assert app['metadata']['namespace'] == project['metadata']['namespace']
assert app['spec']['destination'] in project['spec']['destinations'], 'Project destination mismatch'
assert all(s['repoURL'] in project['spec']['sourceRepos'] for s in sources), 'Project source mismatch'
assert 'automated' not in app['spec'].get('syncPolicy', {}), 'Initial registration must use manual sync'
serialized = yaml.safe_dump_all([app, project], sort_keys=False)
assert not any(p in serialized for p in ('example.invalid', 'github.com/example/', 'REPLACE_WITH_')), 'Replace all example settings first'
for url in [s['repoURL'] for s in sources] + [app['spec']['destination']['server']]:
    assert urlparse(url).password is None, 'Do not embed credentials in URLs'
print(yaml.safe_dump(app, sort_keys=False))
PYTHON
python3 scripts/validate.py --production --mode "$mode" -f "$values_file"
deploy_server=$(python3 - "$tmp_file" <<'PYTHON'
import sys, yaml
with open(sys.argv[1]) as f:
    print(yaml.safe_load(f)['spec']['destination']['server'])
PYTHON
)
python3 scripts/preflight.py -f "$values_file" --server "$deploy_server"
argocd proj create --file "$project_file"
argocd app create --file "$tmp_file"
echo 'Application registered without automatic sync. Review its diff in central Argo CD before syncing.'
