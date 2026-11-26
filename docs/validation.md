# Validation and release evidence

[Documentation](README.md) / Validation

Each check answers a different question. Keep environment-specific execution results, manifests and registry publication records in private storage.

| Check | What it establishes | What it does not establish |
| --- | --- | --- |
| Helm lint and profile validation | Renderable chart, expected topology and security invariants | Runtime connectivity or capacity |
| Credential/public-data guards | Detection of selected accidental disclosure patterns | Proof that no sensitive data exists, automatic revocation or Git history cleanup |
| Maven tests | Exercised retry, offset and payload behavior | Real provider compatibility or sustained throughput |
| Container smoke tests | Packaged classes, runtime startup and selected TLS behavior | OpenShift scheduling or end-to-end CDC delivery |
| Read-only preflight | Required platform state and identity enrollment at check time | Successful deployment |
| Server dry-run | API/admission acceptance without persistence | Controller reconciliation or policy enforcement |
| Staging acceptance | Observed behavior under your deployment conditions | Untested failures or future releases |

## Local checks

```bash
make validate
mvn -B -ntp -f camel-s3/pom.xml verify
mvn -B -ntp -f camel-connect/pom.xml verify
```

The manifest validator checks all five modes. It requires native Kafka internal listeners, rejects Kafka/namespace waypoint enrollment, and checks STRICT mTLS plus HTTP waypoint authorization. Profile counts can change as the chart evolves.

## Image smoke checks

After building the images, set `IMAGE_PREFIX` and `IMAGE_TAG` to your published release. `JAVA_HOME` must point to an appropriate JDK.

```bash
PLATFORMS=linux/amd64,linux/arm64 bash scripts/smoke-connect-images.sh
for platform in linux/amd64 linux/arm64; do
  IMAGE="${IMAGE_PREFIX}camel-s3:${IMAGE_TAG}" PLATFORM="$platform" \
    python scripts/smoke-camel-image.py
done
```

The Connect harness exercises plugin classloader isolation. The Camel packaging smoke script uses a temporary local HTTPS stub, disposable test certificate and synthetic test values; it is optional and does not use production credentials. Do not run it if your environment prohibits generating disposable test material. These tests are not substitutes for live Kafka/PostgreSQL/S3 acceptance.

## Platform checks

```bash
python scripts/validate.py --production --mode all -f .local/values.yaml
python scripts/preflight.py -f .local/values.yaml
```

Preflight uses your existing local `oc` and `argocd` sessions. It checks the issuer/store, APIs, storage, workers, ambient configuration and caller enrollment. It reads no Kubernetes Secret objects. The target API defaults to the authenticated `oc` server; use `--server` to assert the expected destination explicitly.

For server dry-run, render private values into ignored storage and use the correct target namespace under your platform's validation process. Dry-run does not persist resources; it may need an existing namespace. Keep output private.

Then complete [the production acceptance gates](operations.md#acceptance-gates), including actual mTLS rejection tests, direct-pod HTTP bypass tests, certificate rotation, failover, load, S3 interruption and offset recovery. No supplied manifest or documentation claims that these environment-specific tests have already passed.

## Public repository checks

```bash
python scripts/check-sensitive-data.py --history
python scripts/check-public.py --history
python scripts/test-publication-guards.py
python scripts/check-docs.py
git diff --cached --stat
git diff --cached
```

`.local/`, private environment overlays, credentials, kubeconfigs and build output are ignored. Ignore rules do not remove already tracked files, erase Git history or prevent `git add -f`. The dedicated [Sensitive data workflow](../.github/workflows/sensitive-data.yaml) checks current files and fetched history. The public-data guard rejects tracked private locations and common environment-data patterns; maintainers must still review staged changes and publication history. See [Publication safety](publication-safety.md) for installing the pinned scanner and adding an ignored organization-specific deny list.

The docs checker verifies local links and required diagram blocks. Diagrams are Mermaid source rendered by GitHub; no external image tracking or hosted diagram service is required.
