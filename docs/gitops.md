# Deploy with central Argo CD

[Documentation](README.md) / GitOps deployment

Use your existing central Argo CD instance and registered target cluster. Keep reusable implementation public and deployment-specific values private.

## Repository layout

| Location | Contents | Visibility |
| --- | --- | --- |
| This project | Helm chart, application code, build tooling, generic examples and guides | Public |
| Your environment repository | Values, target API URL, registry references, Application/AppProject and deployment evidence | Private |
| Vault | Passwords, access keys and required trust bundles | Restricted secret storage |
| `.local/` | Local preparation copies and inspection notes | Ignored; never an Argo source |

[`gitops/application.yaml`](../gitops/application.yaml) uses Argo CD's [multiple-source support](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/): one pinned Git commit provides the chart and a second pinned commit provides `$values` from private Git. The private source has `ref: values` and no manifest `path`.

Copy the Application and [AppProject](../gitops/project.yaml) into private configuration Git. Replace both repository URLs, both commit placeholders, the target API URL, and the central Argo namespace. Keep the source allowlist and destination restriction aligned. Configure repository credentials through central Argo's approved credential store.

## Build the four images

Requires Java 21, Maven 3.9+, Buildx with amd64/arm64 support, Red Hat registry entitlement and push access to your four image repositories. Authenticate through your normal credential helper; do not pass credentials as build arguments.

```bash
mvn -B -ntp -f camel-s3/pom.xml verify
mvn -B -ntp -f camel-connect/pom.xml verify

# Non-secret shell settings; substitute your registry and immutable release tag.
export IMAGE_PREFIX=registry.example.invalid/team/streamforge-
export IMAGE_TAG=0.1.0

docker buildx build --platform linux/amd64,linux/arm64 --push \
  --target source -f connect/Dockerfile \
  -t "${IMAGE_PREFIX}connect-debezium:${IMAGE_TAG}" .
docker buildx build --platform linux/amd64,linux/arm64 --push \
  --target aiven -f connect/Dockerfile \
  -t "${IMAGE_PREFIX}connect-aiven:${IMAGE_TAG}" .
docker buildx build --platform linux/amd64,linux/arm64 --push \
  --target camel-connect -f connect/Dockerfile \
  -t "${IMAGE_PREFIX}connect-camel:${IMAGE_TAG}" .
docker buildx build --platform linux/amd64,linux/arm64 --push \
  -f camel-s3/Dockerfile \
  -t "${IMAGE_PREFIX}camel-s3:${IMAGE_TAG}" camel-s3
```

These commands **publish images**. Inspect the resulting multi-platform manifests, scan the images, retain SBOMs and pin their index digests in private values. Build success alone does not demonstrate provider compatibility or production readiness. [Image settings →](configuration.md#image-references)

## Prepare platform prerequisites

Complete [the platform checklist](platform-assessment.md), [Vault contract](secrets.md), and [mesh caller enrollment](service-mesh.md). The chart owns only its application Namespace. Shared operator/monitoring namespaces, the mesh control plane, external services and Vault policies belong to their platform owners.

Merge the two supplied health scripts into your **central** Argo configuration:

| Script | Health customization |
| --- | --- |
| [`health.lua`](../gitops/health.lua) | Ready-based Kafka resources, ExternalSecret and Certificate |
| [`gateway-health.lua`](../gitops/gateway-health.lua) | `gateway.networking.k8s.io_Gateway`: current-generation Accepted and Programmed |

For Kafka use the group `kafka.strimzi.io` separately with Kafka, KafkaConnect, KafkaConnector, KafkaTopic and KafkaUser. The other keys are `external-secrets.io_ExternalSecret` and `cert-manager.io_Certificate`. Merge individual customizations; do not replace the shared argocd-cm.

## Validate and register

Import [network metadata from Vault](configuration.md#import-network-settings-from-vault) during environment preparation, review and commit it privately, then pin that environment commit. Use a local copy of the **same values at the pinned private repository commit**. All shell examples assume the release/namespace name `streamforge`.

```bash
python scripts/validate.py --production --mode all -f .local/values.yaml
python scripts/preflight.py -f .local/values.yaml
```

After pushing the reviewed public source commit and private configuration commit, either let the existing platform GitOps process create the configured Application/AppProject or use the explicit helper:

```bash
bash scripts/argocd-create.sh FULL_PUBLIC_GIT_COMMIT all \
  .local/application.yaml .local/project.yaml .local/values.yaml
```

The helper verifies the checked-out public commit, configuration placeholders, project scope, local production validation and target preflight before creating the project/application. It creates no automatic sync. It does not prove that an arbitrary local values file matches private Git; check that correspondence during review.

## Review and sync

Replace the example Application name if you configured a different one:

```bash
argocd app diff streamforge-production
argocd app sync streamforge-production
argocd app wait streamforge-production --health --sync --timeout 900
```

Sync waves establish Namespace enrollment, network/mesh policy, secrets/certificates, HTTP waypoint, Kafka, topics/users, workers and connectors in order. Certificate and ExternalSecret readiness gate dependent workloads.

Namespace, core Kafka resources, node pools and topics have deletion protection. PVCs retain their data, automated pruning is disabled, and the Application has no cascading deletion finalizer. These controls do not replace backups or restrict an administrator's direct storage deletion.

## Operate and promote

- Keep one Application for the namespace and cluster; do not deploy competing Applications for each sink profile.
- Stop a removed connector intentionally, then review removal of its stateless worker and related resources. Preserve group/internal topics and offsets when a showcase will resume.
- Promote by reviewing new public/private commit pins and immutable image digests. Enable automated self-healing only after the environment's acceptance process.
- Treat database DDL, bucket policies and Vault provisioning as externally owned changes, not privileged Argo hooks.
- A Git revert does not guarantee a safe Kafka metadata or connector state-format downgrade.

Continue with [the showcase](showcase.md) and [production acceptance](operations.md#acceptance-gates).
