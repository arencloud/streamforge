# Ambient mTLS and HTTP waypoints

[Documentation](README.md) / Service mesh

Use the existing Red Hat OpenShift Service Mesh ambient installation. The chart configures workload enrollment and application policy; it does not install or reconfigure the shared mesh control plane.

> **Kafka stays on native Streams listeners.**
> No Kafka bootstrap Service, broker Service, broker pod or controller pod is enrolled in a waypoint. Namespace-wide waypoint enrollment is intentionally absent and rejected by validation.

## Traffic policy

| Connection | Enforcement | Waypoint |
| --- | --- | --- |
| Connect/Camel → Kafka, 9093 | Ambient identity policy plus Kafka TLS, SCRAM and ACLs | No |
| Broker/controller/operator Kafka traffic, 9090/9091 | Ambient identity policy plus Streams internal TLS | No |
| Operator and workers → Connect REST, 8083 | STRICT mTLS and allowed caller identities | Yes |
| Monitoring → Kafka metrics, 9404 | STRICT mTLS and monitoring identity | No |
| Monitoring → Connect metrics or Camel HTTP | STRICT mTLS and monitoring identity | Yes |
| RHCL Gateway → dashboard / Keycloak | STRICT workload mTLS and approved Gateway identity | Separate dashboard / identity waypoints |
| Dashboard → Keycloak JWKS | STRICT workload mTLS, exact caller and signing-key path | Identity waypoint |
| Authorino sidecar → Keycloak JWKS | Explicit sidecar mTLS identity allowance | No; documented sidecar exception |
| Applications → external PostgreSQL/S3 | Provider-facing application TLS and credentials | No |

See the [trust-boundary diagram](architecture.md#3-kafka-transport-and-http-policy-are-separate). Mesh mTLS does not automatically extend to external PostgreSQL/S3. Those providers would need a separate client-certificate integration for mutual TLS.

## Match the existing platform

Configure these values in private Git:

- `mesh.discoveryLabelKey` and `mesh.discoveryLabel`: match the mesh's namespace discovery selector.
- `mesh.trustDomain`: match the existing workload identity trust domain.
- `mesh.istioName`, `cniName`, `ztunnelName`: names used by platform preflight.
- Control-plane/certificate namespaces and operator/monitoring service accounts: match the actual installation.

The chart-owned Namespace receives the discovery label and `istio.io/dataplane-mode=ambient`. Namespace PeerAuthentication is STRICT; authorization is deny-by-default with explicit identity/port allow rules. No permissive application or metrics port is introduced.

Existing mesh PKI may use istio-csr and a dedicated Vault-backed Issuer. It is distinct from the configured ClusterIssuer signing Kafka's listener certificate. Kafka's application-internal CA remains managed by Streams. Reuse the platform's approved PKI integration rather than introducing another CA lifecycle.

Namespace discovery and ambient labels enable automatic mesh discovery/capture; they do not inject an application sidecar. The mesh controller supplies the generated waypoint's certificate configuration automatically. `mesh.certificateNamespace` only permits egress to that existing certificate service under this chart's default-deny NetworkPolicy. It neither selects an Issuer nor overrides the mesh CA endpoint. An application with unrestricted egress may need no equivalent explicit network rule.

## HTTP waypoint behavior

The chart creates one HTTP waypoint with two replicas, worker placement, host anti-affinity and a disruption budget. Connect API/headless Services and Connect/Camel pods are explicitly enrolled. `waypoint-for: all` covers Connect REST forwarding to direct pod addresses and metrics scraping; this label describes supported destination types, not namespace-wide enrollment.

At ztunnel, the API policy allows ingress only from the waypoint identity. At the waypoint, a Gateway-attached policy authorizes the original operator, worker or monitoring identity and destination port. The waypoint has no Kafka-port allow rules. Connect workers share an administrative REST trust boundary; restrict connector editing and pod exec accordingly.

NetworkPolicies permit HBONE on 15008 for the intended namespaces and the required discovery/certificate egress. The documented IPv4/IPv6 kubelet probe SNAT exceptions are explicit. Kubelet probes are not a general plaintext application-access exception.

## Required callers must be meshed

Check the Streams operator and monitoring identities before enabling STRICT policy. Their platform owners must provide compatible ambient enrollment and HBONE connectivity. Example labels are:

```yaml
metadata:
  labels:
    mesh.example.com/member: platform
    istio.io/dataplane-mode: ambient
```

Replace the discovery key/value to match the platform. Apply changes through the shared namespace's existing owner, not through this application's chart. Verify `ambient.istio.io/redirection=enabled` on the relevant pods and actual encrypted traffic. Do not blindly relabel or restart operator-managed monitoring. If its enrollment is unsupported, design a dedicated meshed collector; that alternative is not included here.

`python scripts/preflight.py -f .local/values.yaml` checks the configured caller enrollment and capture. It fails when the prerequisites are missing instead of weakening authentication.

## When Connectivity Link is useful

The core CDC pipeline needs no public HTTP API; Kafka bootstrap remains a native Kafka TCP endpoint. The optional `streamforge-edge` chart publishes the order dashboard and a dedicated Keycloak through the existing Red Hat Connectivity Link installation.

The edge chart supplies an Istio Gateway, Coraza, AuthPolicy, RateLimitPolicy and dedicated dashboard/identity waypoints with explicit ingress-to-waypoint routing. See the [public dashboard security diagram](public-dashboard.md). A `kuadrant.io/v1` TLSPolicy can refer to the platform ClusterIssuer for the Gateway server certificate. It does not establish workload identities, Kafka permissions or client-certificate authentication on its own. Do not attach an ingress TLSPolicy to the HBONE waypoint listener.

## Acceptance before promotion

1. Verify bootstrap, broker discovery, all broker endpoints, sustained CDC and failover under ambient. Kafka traffic must remain absent from waypoint telemetry.
2. Verify authorized operator/worker REST access and monitoring scrapes.
3. Deny unrelated meshed callers, unmeshed callers and direct-pod attempts to bypass HTTP policy.
4. Interrupt the HTTP waypoint in staging: HTTP access must fail closed while Kafka data-plane connections continue.
5. Exercise probes, certificate renewal, caller identity changes and one-worker maintenance.

Manifest/admission checks do not establish runtime interoperability or end-to-end vendor certification. Retain deployment-specific results privately.

References: [Red Hat ambient configuration](https://docs.redhat.com/en/documentation/red_hat_openshift_service_mesh/3.2/html/installing/ossm-istio-ambient-mode), [Istio waypoint enforcement](https://istio.io/latest/docs/ambient/usage/waypoint/), [ambient NetworkPolicy](https://istio.io/latest/docs/ambient/usage/networkpolicy/), [Connectivity Link policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.2/html/configuring_and_deploying_gateway_policies/rhcl-config-deploy-gateway-policies).
