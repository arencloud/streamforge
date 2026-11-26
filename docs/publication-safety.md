# Public repository safety

[Documentation](README.md) / Publication safety

Keep this repository reusable: publish source code, charts, tests and example values. Keep deployed domains, private addresses, registry namespaces, cluster inventory and environment values in a private configuration repository. Store credential values in Vault.

## Automated checks

The [Sensitive data workflow](../.github/workflows/sensitive-data.yaml) runs on pull requests, every push and manual dispatch. It has read-only repository permissions, does not use Vault or deployment credentials, and does not upload scan reports.

| Check | Scope |
| --- | --- |
| Gitleaks | Current publication candidates and all commits reachable from fetched Git refs; standard credential rules and recursive decoding |
| Project credential guard | Selected private-key, cluster-token, access-key and credential-URL patterns |
| Public-data guard | Private IPv4/IPv6 addresses, likely deployment URLs, personal filesystem paths, local configuration files and private environment directories; current files and historical file versions reachable from branches, tags and the checkout |
| Guard regression tests | Safe examples pass; synthetic private values and a forced tracked IDE file fail; deleted historical data remains detectable; matched content is not printed |

Gitleaks is pinned to **8.30.1**, with a pinned SHA-256 checksum for its Linux release binary. Its findings are fully redacted. The small project guards print filenames and categories, never matched values. See the [upstream CLI documentation](https://github.com/gitleaks/gitleaks) for its detection model and limitations.

After the workflow has run in GitHub, make **Secrets and private infrastructure** a required check in the protected branch's ruleset. CI runs after code reaches GitHub; it is not a substitute for checking before the first public push. Review changes to workflow and scanner files themselves.

## Before publishing

Install the pinned Gitleaks version from the [official release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), verify the published checksum for your operating system and put `gitleaks` on PATH. Then run:

```bash
python3 scripts/check-sensitive-data.py --history
python3 scripts/check-public.py --history
python3 scripts/test-publication-guards.py
python3 scripts/check-docs.py
git status --short
git diff --cached --stat
```

The scanner exports only Git-tracked and unignored files into a temporary directory. It does not read ignored `.local/` files, runtime Vault values or local authentication stores. The history option checks locally available history; the private-data check covers branches, tags and the checked-out commit, excluding editor/tool checkpoint refs. Fetch all branches/tags you intend to publish before relying on that result. A new repository without commits still receives a complete current-file scan.

Use an ignored local deny list for organization-specific identifiers that generic checks cannot recognize. Put one private term per line in `.local/publication-deny.txt`, using your editor. Include your real DNS suffix, cluster names, internal repository/registry identifiers and personal identifiers as appropriate. Do not put that list in Git or public workflow configuration.

```bash
python3 scripts/check-public.py --history --deny-file .local/publication-deny.txt
```

The deny list is optional and local; GitHub uses the generic checks without receiving private identifiers. No scanner can prove that arbitrary text contains no sensitive information. Review staged changes as well as scan results.

## Ignore rules and findings

`.gitignore` excludes IDE settings, local overlays, environment files, credentials, kubeconfigs, private-key/truststore files and generated output. Ignore rules do not untrack existing files or erase history. Use `git rm --cached -- PATH` to exclude a tracked local file while preserving its working copy.

If a check fails, inspect the identified file locally. Replace environment details with documented examples or move configuration into private Git. If an actual credential was exposed, revoke or rotate it; deleting it in a later commit does not remove the earlier exposure. Review and clean publication history before publishing it. Avoid pasting the finding or an unredacted scan report into an issue.

Field names, example Vault paths and example DNS names belong in public documentation. Populated credentials and live environment inventory do not. Use the [Vault layout guide](vault-layout.md) and [field-only inventory](examples/vault-layout.yaml) for provisioning references.
