# Platform readiness checklist

[Documentation](README.md) / Platform readiness

Use this checklist for your own environment. Record inventory, addresses, measured capacity and approval evidence in private configuration Git—not in this public project.

## Platform prerequisites

| Area | Confirm before deployment |
| --- | --- |
| OpenShift and Streams | Vendor-supported combination; installed operator watches the target namespace |
| Kafka API | Required `kafka.strimzi.io/v1` resources are served; configured Kafka/metadata versions match the operator mapping |
| ESO | `external-secrets.io/v1` is served; chosen ClusterSecretStore is Ready and restricted appropriately |
| cert-manager | Chosen ClusterIssuer is Ready; signing role permits Kafka service DNS SANs, usages and lifetime |
| Central Argo CD | Target is registered and healthy; repository credentials and resource allowlists are configured |
| Ambient mesh | Compatible operator, healthy Istio/CNI/ztunnel, accepted waypoint class, correct discovery selector and trust domain |
| Mesh clients | Streams operator and monitoring caller identities can authenticate under STRICT mTLS |
| Storage | Retained, expandable block storage with tested fsync latency, capacity, durability and recovery |
| Scheduling | At least three suitable workers, capacity for requested resources, upgrades and a failure scenario |
| Monitoring | Required metrics are queryable; alert routing and remote-write/federation cover the application |
| External PostgreSQL | Logical replication, publication, role, slot/WAL monitoring and verified TLS |
| External S3 | Private bucket, prefix IAM, HTTPS, encryption, lifecycle and required API compatibility |

## Version baseline

Build files pin Kafka 4.2.0, Red Hat build of Debezium 3.6.3.Final-redhat-00009, Aiven 3.4.4, the Red Hat Camel/Quarkus platform BOM 3.27.6.SP3-redhat-00002, and Java 21. These are reproducibility inputs, not a claim that every combination is currently supported or vulnerability-free. Check your vendor support matrix, operator mappings, dependency licenses and security errata for each release.

The public repository does not install shared operators or infer support from their presence. Red Hat-built libraries do not make the Aiven plugin or custom Camel Connect adapter Red Hat-supported products.

## Capacity and failure domains

The default topology has three controller-only nodes, three broker-only nodes, two workers per Connect cluster and two Camel replicas in the full showcase. The HTTP waypoint adds two replicas. ResourceQuota and LimitRange provide boundaries; verify actual scheduling requests, transient rollout headroom and JVM sizing against your platform.

Host anti-affinity does not provide zone/site resilience. Shared storage can be a common failure domain. With only three workers, replacing a failed member or draining a worker may need a spare worker; respect disruption budgets and never force a drain past quorum protections.

Kafka retention must cover your maximum tolerated sink outage. S3 CDC archives are not a full Kafka backup or a PostgreSQL backup. Define recovery objectives and exercise the restore process independently.

## Evidence to keep privately

Record observed operator/API versions, readiness, storage/topology, approved network ranges, certificate policy, tested release digests, acceptance results and outstanding support questions. Do not include Secret data, login tokens, database exports or resolved connector configurations in reports.

[Validation procedure →](validation.md) · [Operations and acceptance →](operations.md)
