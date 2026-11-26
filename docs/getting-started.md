# Getting started

[Documentation](README.md) / Getting started

Start with a local preview. Then prepare a private environment overlay and deploy through your existing central Argo CD instance.

## Before you begin

| Requirement | Used for |
| --- | --- |
| Helm 3 and Python 3.9+ | Render and validate manifests |
| Java 21 and Maven 3.9+ | Build and test the Camel applications |
| Docker Buildx | Publish amd64/arm64 images |
| Authenticated `oc` and `argocd` CLIs | Read-only platform checks and GitOps operations |
| Red Hat registry entitlement | Pull the Streams base image |

The target platform needs a compatible Red Hat Streams operator, ESO with a ready ClusterSecretStore, cert-manager with a ready ClusterIssuer, block storage, monitoring, and a configured ambient mesh. PostgreSQL, S3 and Vault are supplied externally. Use the [platform checklist](platform-assessment.md) to confirm compatibility and ownership.

## 1. Preview the public example

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r scripts/requirements.txt
make validate
make render MODE=all
```

No cluster connection or credentials are needed. Use `MODE=aiven`, `MODE=camel` or `MODE=camel-connect` to preview a single sink. Example endpoints intentionally fail production validation.

## 2. Prepare a private overlay

```bash
mkdir -p .local
cp environments/example/values.yaml .local/values.yaml
```

Edit `.local/values.yaml` using the [configuration reference](configuration.md). Set the issuer/store names, storage class, mesh discovery/trust settings, destination CIDRs, the PostgreSQL egress port and all four image digests; put PostgreSQL runtime connection fields and per-sink S3 settings in Vault. The namespace and release name used in these guides are `streamforge`.

`.local/` is ignored; it is a preparation area, not a source Argo CD can read. Put the final environment values and configured Application/AppProject in a **private Git repository**. Keep credential values in Vault.

## 3. Prepare services and secrets

- Ask the DBA to configure logical replication, the dedicated CDC role, publication, slot permissions and TLS.
- Provision a private S3 bucket and independent credentials scoped to each sink prefix.
- Populate the [Vault field contract](secrets.md) through your approved tooling.
- Verify the signing role permits the internal Kafka DNS SANs and requested certificate lifetime.
- Verify the Streams operator and monitoring clients can satisfy [ambient STRICT mTLS](service-mesh.md).

## 4. Build, pin and validate

Follow [the build instructions](gitops.md#build-the-four-images), then replace `build-required` references with immutable image digests in the private overlay.

```bash
# With an authenticated Vault CLI; imports network metadata only:
python scripts/import-network-values.py --values .local/values.yaml
python scripts/validate.py --production --mode all -f .local/values.yaml
python scripts/preflight.py -f .local/values.yaml
```

The import command prepares local network values without deploying. The validator checks rendered configuration locally. Preflight reads the authenticated cluster and central Argo CD state without fetching Secrets. It reports unmet platform prerequisites; it does not install or change them.

## 5. Deploy and demonstrate

Follow [the central Argo CD deployment guide](gitops.md). Review the Application diff before syncing. Once the resources are ready, run [the showcase](showcase.md) and compare all three outputs.

Production promotion additionally requires the [acceptance gates](operations.md#acceptance-gates): successful schema validation is not a substitute for end-to-end delivery, failure, renewal and load testing.
