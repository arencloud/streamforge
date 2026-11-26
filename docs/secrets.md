# Secrets and certificates

[Documentation](README.md) / Secrets and certificates

For a complete provisioning checklist including the optional dashboard and Keycloak, use [Suggested HashiCorp Vault layout](vault-layout.md) and its [field-only YAML inventory](examples/vault-layout.yaml).

## Vault field contract

ESO reads KV v2 keys **relative to the mount configured in your ClusterSecretStore (the examples use `secret`)**. Do not include `secret/data/` in ExternalSecret remote keys. The table contains field names, never example credential values.

The example prefix is `streamforge` (`vaultPrefix`); change it in private values when your mount uses another project prefix. The paths below include the example `secret` mount for Vault UI/CLI usage. ESO remote keys omit that mount and the KV v2 `data/` segment.

| Vault path | Fields |
| --- | --- |
| `secret/streamforge/kafka/source` | `KAFKA_SOURCE_PASSWORD` |
| `secret/streamforge/kafka/aiven` | `KAFKA_AIVEN_PASSWORD` |
| `secret/streamforge/kafka/camel` | `KAFKA_CAMEL_QUARKUS_PASSWORD` |
| `secret/streamforge/kafka/camel-connect` | `KAFKA_CAMEL_CONNECT_PASSWORD` |
| `secret/streamforge/trust` | `KAFKA_CA_PEM` |
| `secret/streamforge/s3/aiven` | `S3_AIVEN_ACCESS_KEY_ID`, `S3_AIVEN_SECRET_ACCESS_KEY`, plus the shared field names below |
| `secret/streamforge/s3/camel` | `S3_CAMEL_QUARKUS_ACCESS_KEY_ID`, `S3_CAMEL_QUARKUS_SECRET_ACCESS_KEY`, plus the shared field names below |
| `secret/streamforge/s3/camel-connect` | `S3_CAMEL_CONNECT_ACCESS_KEY_ID`, `S3_CAMEL_CONNECT_SECRET_ACCESS_KEY`, plus the shared field names below |
| `secret/streamforge/postgres` | `PG_CDC_USERNAME`, `PG_CDC_PASSWORD`, `PG_CA_PEM`, `PG_DATABASE`, `PG_HOST`, `PG_PORT` |

### PostgreSQL fields and network policy

| Vault field | Consumer |
| --- | --- |
| `PG_CDC_USERNAME` | Debezium database user, via `postgres-credentials/username` |
| `PG_CDC_PASSWORD` | Debezium database password, via `postgres-credentials/password` |
| `PG_CA_PEM` | PEM CA bundle mounted at `/mnt/postgres-ca/ca.crt`; `verify-full` remains mandatory |
| `PG_DATABASE` | Database name, resolved through the worker's `PG_DATABASE` environment variable |
| `PG_HOST` | Hostname/address matching the PostgreSQL server certificate |
| `PG_PORT` | Runtime connection port; must equal `network.postgresPort` |
| `PG_EGRESS_CIDRS` | Provisioning metadata; mirror approved CIDRs into private `network.postgresCidrs` values |
| `PG_CA` | Unused; `PG_CA_PEM` is the canonical CA field |
| `PG_CONNECTION_STRING` | Unused; the connector uses separate connection fields |

ESO fetches only the six runtime fields. It does not copy a connection string, duplicate CA field or network inventory into workload Secrets. NetworkPolicy cannot reference Secret data, so CIDRs and the allowed port are rendered from private GitOps values. ESO rejects a `PG_PORT` that differs from `network.postgresPort`. Update the policy and Vault configuration together when moving the database. Actual CIDRs remain in private configuration Git, never the public example.

Legacy `postgres.host`, `postgres.database` and `postgres.port` Helm values are rejected. Host/database now come from Vault; the separately reviewed policy port is `network.postgresPort` (example default `5432`). Table, publication, replication slot and topic settings remain in Helm.

### S3 fields

Each **S3 entry** also contains these fields:

| Field | Requirement |
| --- | --- |
| `S3_BUCKET` | Existing bucket; may be the same for all sinks or different per sink |
| `S3_ENDPOINT` | HTTPS endpoint without embedded credentials, path, query or fragment |
| `S3_REGION` | Non-empty provider region |
| `S3_PATH_STYLE` | Lowercase `true` or `false`; Aiven requires `true` with a custom endpoint |
| `S3_CA_CERTIFICATE_PEM` | PEM CA bundle for that sink's object-store endpoint |
| `S3_EGRESS_CIDRS` | Approved destination CIDRs for this sink; imported into its private NetworkPolicy values |

ESO maps these uppercase Vault properties into stable Kubernetes Secret keys consumed by the applications. Kafka passwords map to `password`; S3 access keys map to `access-key-id` and `secret-access-key`; S3 settings map to `bucket`, `endpoint`, `region` and `path-style`; each S3 CA maps to `ca.crt`. `KAFKA_CA_PEM` becomes `external-trust/kafka-ca.crt`.

S3 connection settings are resolved from Vault at runtime, not from Helm endpoint/bucket values. `S3_EGRESS_CIDRS` is provisioning metadata and is not copied into workload Secrets; the [local import step](configuration.md#import-network-settings-from-vault) prepares separate egress policies. The ESO templates reject invalid endpoint, bucket, region and path-style settings using [v2 strict missing-key evaluation](https://external-secrets.io/latest/guides/templating/); validation error keys contain no provider values. Invalid updates leave the last successfully synchronized Secret in place, so monitor ExternalSecret readiness and freshness. Do not print resolved connector configuration while checking readiness.

Store **field names without `=`** in Vault. Values must be populated, not empty placeholders. Kafka passwords must be single-line and satisfy SCRAM requirements. `KAFKA_CA_PEM` must contain the Kafka listener's root/intermediate trust chain. Each S3 CA must trust its provider; do not assume it uses the Kafka CA. Never place a CA private key in these entries.

## Certificate ownership

cert-manager generates a separate RSA listener private key and asks the configured ClusterIssuer to sign its certificate. The role must allow both bootstrap service names and wildcard broker service SANs in namespace `streamforge`, server-auth usage and a 90-day lifetime (or reduce `duration` to the permitted maximum). Confirm issuance in staging. cert-manager's `ca.crt` is not relied upon as an automatically complete root bundle.

The signing role must permit the names requested by [certificate.yaml](../charts/streamforge/templates/certificate.yaml), including `.svc` and `.svc.cluster.local` bootstrap/broker names. Permission for a corporate domain does not automatically authorize Kubernetes service names. Certificate SANs must match the names clients actually use; changing SANs alone does not configure DNS or Kafka advertised addresses.

**PKI boundary:** Kafka's client listener chains to Vault. Streams continues to manage its own internal cluster and clients CAs for broker/controller/operator traffic; they are not Vault-rooted in this baseline. If policy requires every internal Kafka certificate to chain to Vault, qualify externally supplied intermediate cluster/client CAs with the installed operator and a dedicated rotation process before promotion. Do not assume the listener signing role permits intermediate CA issuance.

Ambient transport adds a separate mTLS layer through the platform's existing mesh CA integration. Set `mesh.trustDomain` to the actual workload trust domain. Kafka bootstrap, broker and controller traffic does not traverse a waypoint. HTTP waypoints protect Connect REST and Camel endpoints only; see [the mesh guide](service-mesh.md). A Connectivity Link TLSPolicy does not replace workload identity issuance.

## Access boundaries

ESO materializes Kubernetes Secrets; it does not remove the need for encryption of Kubernetes API storage, namespace RBAC and restricted access to pod exec/debug. Confirm platform encryption-at-rest settings. Restrict the ClusterSecretStore and its Vault policy to the intended namespaces and project paths. Project provisioning should grant KV read access only for `secret/data/streamforge/*` (metadata access only if required by provisioning). ESO and cert-manager authentication remains managed by the platform.

Kafka ACLs scope writers/readers to the CDC topic, source heartbeat and their own internal topics/groups. No superuser or application wildcard topic ACLs are granted. Connect API endpoints are cluster-internal with NetworkPolicy access limited to the namespace and operator namespace. Treat pod creation/exec and connector editing in this namespace as privileged operations: Connect config providers expose worker environment credentials to trusted connector configuration.

PostgreSQL must offer TLS with a matching DNS SAN; `verify-full` is mandatory. The DBA creates a dedicated LOGIN REPLICATION role and grants SELECT only on captured tables and UPDATE on the single heartbeat row. Publications are explicitly provisioned; no automatic `FOR ALL TABLES` permissions. The source needs a durable logical slot, adequate WAL retention and `wal_level=logical`. The heartbeat table is in the publication so a quiet captured table does not indefinitely stall WAL acknowledgement.

For S3, pre-create the bucket, block public access, enforce HTTPS and default server-side encryption, and set retention/lifecycle. Give Aiven only its `aiven/` prefix and Quarkus only its `camel/` prefix and custom Connect only its `camel-connect/` prefix. Aiven needs PutObject, GetObject, AbortMultipartUpload and multipart-list permissions as documented upstream; scope object and bucket actions correctly. Camel performs PutObject and bucket existence checks (HeadBucket commonly requires ListBucket); give only required bucket metadata/list and its prefix PutObject. Add KMS permissions only if the chosen encryption requires them. Aiven 3.4.4 forces path-style requests when its custom endpoint is configured; Camel's path style is configurable. Confirm provider compatibility before deployment.

## Rotation

Secrets refresh every five minutes. S3 endpoint/bucket/region/addressing changes require the same controlled consumer rollout as credential changes; update the relevant egress CIDRs before changing providers. Environment variables, SDK clients, Java truststores and SASL sessions do **not** all reload live. Rotate with an overlap window where possible, confirm ExternalSecrets Ready and KafkaUsers Ready, increment `rotationRevision` in Git and sync to roll Connect/Camel. Streams watches the listener Secret and reconciles certificate renewal. Validate actual renewal/rolling behavior. For a root change, distribute a bundle with old and new roots first, roll consumers, issue the new leaf, verify, then remove old trust in a later rollout. A single SCRAM password change may cause transient reauthentication failures; dual identities are needed for a strict zero-downtime rotation requirement.

Keep credential values out of Git, chat, shell arguments and rendered reports. Use your approved Vault provisioning tooling. This guide lists fields and references only; it does not generate passwords or access keys.
