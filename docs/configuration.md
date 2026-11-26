# Configuration reference

[Documentation](README.md) / Configuration

The complete defaults live in [`charts/streamforge/values.yaml`](../charts/streamforge/values.yaml). Start from [`environments/example/values.yaml`](../environments/example/values.yaml) and keep your overrides private.

## Environment settings

| Values key | Set it to |
| --- | --- |
| `issuer` | Your existing Vault-backed ClusterIssuer name |
| `secretStore` | Your existing ESO ClusterSecretStore name |
| `vaultPrefix` | KV key prefix, relative to the store's configured mount |
| `kafka.storageClass` | Retained, expandable block-storage class qualified for Kafka |
| `kafka.version`, `kafka.metadataVersion` | A compatible pair supported by your Streams operator |
| `network.operatorNamespace` | Namespace running the Streams Cluster Operator |
| `network.apiCidrs` | Kubernetes API service/backend destination CIDRs |
| `network.postgresCidrs` | Approved PostgreSQL destinations from `PG_EGRESS_CIDRS` |
| `network.s3Cidrs.aiven`, `.camel`, `.camel-connect` | Separate approved S3 destinations from each entry's `S3_EGRESS_CIDRS` |
| `network.postgresPort` | PostgreSQL egress port, matching `PG_PORT` in Vault |
| `postgres.table`, `topicPrefix`, `topic` | Captured table and its matching Kafka topic |
| `postgres.slot`, `publication` | Durable replication slot and DBA-managed publication |
| `imagePullSecrets` | Names of existing pull Secrets when registry access requires them |

PostgreSQL runtime host, port, database, credentials and CA come from the [Vault contract](secrets.md#postgresql-fields-and-network-policy). Mirror the approved `PG_EGRESS_CIDRS` inventory into private `network.postgresCidrs`; Kubernetes cannot resolve it from a Secret.

Example-only addresses must be replaced before deployment. Do not widen egress to every address to bypass an unknown provider range. Verify both Service VIP and backend traffic against your CNI's NetworkPolicy behavior.

## Import network settings from Vault

Each sink's Vault entry carries its own `S3_EGRESS_CIDRS`. NetworkPolicy cannot resolve runtime Secret references, so the network inventory must also be available to Helm in private configuration Git. Use the import helper with an authenticated local Vault CLI:

```bash
python scripts/import-network-values.py --values .local/values.yaml --mount secret
```

It reads `PG_EGRESS_CIDRS` and `PG_PORT` from the PostgreSQL entry, and `S3_EGRESS_CIDRS` from all three S3 entries under `vaultPrefix`. The CLI filters output to each selected field; the helper does not print network values or credential fields. CIDRs may be a JSON array or a comma/newline-separated string. Include explicit prefixes, such as `/32` for an IPv4 host or `/128` for an IPv6 host. Empty, malformed, unrestricted and documentation-only destination ranges are rejected.

Every field is validated before the helper atomically updates the ignored local values file with mode `0600`. On a read/validation failure the destination remains unchanged. The command creates no credentials, cluster resources or Git commits. Review the resulting network changes privately and transfer them to the private repository at the Application's pinned environment commit. This is an explicit import, not continuous synchronization from Vault.

The chart renders one egress policy per active sink, so one sink's ranges do not grant direct S3 access to the other sinks. HTTPS egress remains on port 443. When upgrading an older deployment that still has the combined `sinks-s3` NetworkPolicy, review and remove that old policy after the new per-sink policies are active; Kubernetes policies are additive and Argo pruning is manual here.

## Mesh settings

| Values key | Meaning |
| --- | --- |
| `mesh.enabled` | Enables ambient enrollment and policy; required by the production validator |
| `mesh.discoveryLabelKey`, `mesh.discoveryLabel` | Namespace label matching your Istio discovery selector |
| `mesh.trustDomain` | Existing mesh trust domain; must match workload certificate identities |
| `mesh.istioName`, `cniName`, `ztunnelName` | Existing Sail resources checked by preflight |
| `mesh.controlPlaneNamespace`, `certificateNamespace` | Namespaces used for waypoint discovery/certificate egress |
| `mesh.operatorServiceAccount` | Streams operator identity allowed to use Connect REST and native Kafka operator ports |
| `mesh.monitoringNamespace`, `monitoringServiceAccount` | Meshed monitoring caller identity |
| `mesh.waypointName`, `waypointReplicas`, `waypointResources` | HTTP waypoint placement and capacity |

The supplied discovery label is an example. Neither the chart nor preflight installs or reconfigures the shared mesh. The current preflight expects a `matchLabels` discovery selector; qualify more complex selector layouts separately.

## Image references

Build and publish four repositories in your own registry:

| Values key | Image repository suffix | Build source |
| --- | --- | --- |
| `connect.sourceImage` | `streamforge-connect-debezium` | `connect/Dockerfile`, target `source` |
| `connect.aivenImage` | `streamforge-connect-aiven` | `connect/Dockerfile`, target `aiven` |
| `connect.camelImage` | `streamforge-connect-camel` | `connect/Dockerfile`, target `camel-connect` |
| `camel.image` | `streamforge-camel-s3` | `camel-s3/Dockerfile` |

Use an immutable multi-platform index reference such as `registry.example.invalid/team/image@sha256:<digest>`, replacing the entire example with the published reference. Store image publication records and deployment-specific index/child digests in private configuration Git.

## Bucket and prefix contract

Each sink reads its bucket, endpoint, region, path style and CA from its own Vault entry. Use the same bucket in all three entries for the shared-bucket showcase, or distinct buckets without changing the chart. Helm configures only the object prefixes:

| Key | Default |
| --- | --- |
| `s3.aivenPrefix` | `aiven/` |
| `s3.camelPrefix` | `camel/` |
| `s3.camelConnectPrefix` | `camel-connect/` |

Prefixes must end with `/`. Use separate S3 credentials for each sink. Bucket creation, encryption, lifecycle and IAM policies are managed externally. See the [exact Vault fields](secrets.md#vault-field-contract). Legacy `s3.endpoint`, `s3.region`, `s3.bucket` and `s3.pathStyle` Helm values are rejected by the schema; remove them from private overlays.

## Profiles and lifecycle

Select `aiven`, `camel`, `camel-connect`, `both` or `all` using `mode`. Keep one Argo Application per Kafka deployment so profiles do not compete for shared resources. Removing a sink from values does not automatically prune its resources; review the [profile transition procedure](gitops.md#operate-and-promote).

Increment `rotationRevision` after the required credential/trust rotation steps to roll consumers. Runtime environment variables and SDK clients do not all reload automatically. [Rotation procedure →](secrets.md#rotation)
