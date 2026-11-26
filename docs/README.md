# Documentation

[← Project overview](../README.md)

Follow the setup path once, then use the reference guides as needed.

## Setup path

**[1. Understand the architecture](architecture.md)** → **[2. Prepare your environment](getting-started.md)** → **[3. Configure Vault and TLS](secrets.md)** → **[4. Deploy with Argo CD](gitops.md)** → **[5. Run the showcase](showcase.md)**

| Guide | What you will find |
| --- | --- |
| [Architecture](architecture.md) | Data flow, GitOps reconciliation and trust-boundary diagrams |
| [Getting started](getting-started.md) | Prerequisites, safe local preview and setup order |
| [Configuration](configuration.md) | Values to change, image names, profiles and private overlays |
| [Vault layout](vault-layout.md) | Suggested KV v2 paths, complete field-only inventory and consumer boundaries |
| [Publication safety](publication-safety.md) | GitHub secret scanning, private-data guards and pre-publication checks |
| [Secrets and certificates](secrets.md) | Vault paths/fields, CA ownership and rotation |
| [GitOps deployment](gitops.md) | Multi-platform builds, public chart/private values, sync and promotion |
| [Service mesh](service-mesh.md) | Ambient enrollment, HTTP waypoints, identity policy and Connectivity Link scope |
| [Showcase](showcase.md) | Synthetic PostgreSQL changes and three-way S3 verification |
| [Operations](operations.md) | Retry semantics, observability, failure recovery and acceptance gates |
| [Platform checklist](platform-assessment.md) | An environment-neutral qualification checklist |
| [Validation](validation.md) | Reproducible checks and what they do—and do not—prove |

## Example conventions

`example.invalid`, `example.com`, `cluster.local` and `192.0.2.0/24` are illustrative settings, not deployment instructions. Issuer, secret-store, storage-class and namespace names must match your platform. Copy examples into an ignored local directory for preparation and a **private configuration repository** for GitOps deployment.

These guides contain no live cluster inventory or credentials. Keep operational evidence, addresses, image publication records and support assessments private.

- [Order lifecycle dashboard](order-dashboard.md) — interactive orders and three-sink delivery observation.

- [Public dashboard deployment](public-dashboard.md) — RHCL, Keycloak, Coraza, TLS, authentication and rate limits.
