#!/usr/bin/env python3
"""Read-only checks. Never fetch Secret objects or credential-bearing configuration."""
import json
import argparse
import pathlib
import subprocess
import sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def merge(base, overlay):
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value


def get(*args):
    return json.loads(subprocess.check_output(["oc", "get", *args, "-o", "json"], text=True))


def ready(obj):
    return any(c["type"] == "Ready" and c["status"] == "True" for c in obj.get("status", {}).get("conditions", []))


try:
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--values", action="append", required=True, help="Private environment values; repeat to merge overlays")
    parser.add_argument("--server", help="Expected target API URL; defaults to the authenticated oc server")
    args = parser.parse_args()
    values = yaml.safe_load((ROOT / "charts/streamforge/values.yaml").read_text())
    for path in args.values:
        merge(values, yaml.safe_load(pathlib.Path(path).read_text()) or {})
    current_server = subprocess.check_output(["oc", "whoami", "--show-server"], text=True).strip()
    target_server = args.server or current_server
    assert target_server == current_server, "oc context does not match the intended target API"
    for kind, name in [("clusterissuer", values["issuer"]), ("clustersecretstore", values["secretStore"])]:
        assert ready(get(kind, name)), f"{kind}/{name} is not ready"
        print(f"{kind}/{name}: Ready")
    for name in ["kafkas.kafka.strimzi.io", "kafkaconnects.kafka.strimzi.io", "externalsecrets.external-secrets.io"]:
        assert any(v["name"] == "v1" and v["served"] for v in get("crd", name)["spec"]["versions"])
        print(f"{name}: v1 served")
    sc = get("storageclass", values["kafka"]["storageClass"])
    assert sc["reclaimPolicy"] == "Retain" and sc["allowVolumeExpansion"]
    workers = get("nodes", "-l", "node-role.kubernetes.io/worker")["items"]
    assert len([n for n in workers if ready(n) and not n.get("spec", {}).get("unschedulable")]) >= 3
    print("At least three Ready, schedulable workers; retained expandable storage available")
    if values["mesh"]["enabled"]:
        mesh = values["mesh"]
        for name in ["gateways.gateway.networking.k8s.io", "authorizationpolicies.security.istio.io", "peerauthentications.security.istio.io"]:
            assert any(v["name"] == "v1" and v["served"] for v in get("crd", name)["spec"]["versions"])
        for kind, name in [("istios.sailoperator.io", mesh["istioName"]), ("istiocnis.sailoperator.io", mesh["cniName"]), ("ztunnels.sailoperator.io", mesh["ztunnelName"])]:
            assert ready(get(kind, name)), f"{kind}/{name} is not ready"
        istio = get("istios.sailoperator.io", mesh["istioName"])["spec"]
        assert istio["profile"] == "ambient"
        assert istio["values"]["meshConfig"]["trustDomain"] == mesh["trustDomain"], "Mesh trust domain mismatch"
        assert any(s.get("matchLabels", {}).get(mesh["discoveryLabelKey"]) == mesh["discoveryLabel"] for s in istio["values"]["meshConfig"]["discoverySelectors"]), "Mesh discovery selector mismatch"
        gateway_class = get("gatewayclass", "istio-waypoint")
        assert any(c["type"] == "Accepted" and c["status"] == "True" for c in gateway_class.get("status", {}).get("conditions", []))
        clients = [(values["network"]["operatorNamespace"], mesh["operatorServiceAccount"])]
        if values["monitoring"]["enabled"]:
            clients.append((mesh["monitoringNamespace"], mesh["monitoringServiceAccount"]))
        missing = []
        for namespace, service_account in clients:
            labels = get("namespace", namespace)["metadata"].get("labels", {})
            if labels.get(mesh["discoveryLabelKey"]) != mesh["discoveryLabel"] or labels.get("istio.io/dataplane-mode") != "ambient":
                missing.append(f"{namespace}: enroll the required clients in ambient through their platform GitOps owner")
                continue
            # Fetch only names, service-account names and ambient capture status, never env/Secret data.
            rows = subprocess.check_output([
                "oc", "get", "pods", "-n", namespace, "-o",
                'jsonpath={range .items[*]}{.metadata.name}{"\\t"}{.spec.serviceAccountName}{"\\t"}{.metadata.annotations.ambient\\.istio\\.io/redirection}{"\\n"}{end}'
            ], text=True).splitlines()
            clients_status = [row.split("\t") for row in rows if row.split("\t")[1:2] == [service_account]]
            if not clients_status or any(row[2:] != ["enabled"] for row in clients_status):
                missing.append(f"{namespace}/{service_account}: ambient capture is not confirmed for all client pods")
        assert not missing, "Strict mTLS prerequisites:\n" + "\n".join(missing)
        print("Ambient control plane ready; operator and monitoring clients captured; waypoint class Accepted")
    data = json.loads(subprocess.check_output(["argocd", "cluster", "list", "-o", "json"], text=True))
    target = next(c for c in data if c["server"] == target_server)
    assert target["connectionState"]["status"] == "Successful"
    print("Central Argo CD: target cluster connection Successful")
except (AssertionError, subprocess.CalledProcessError, StopIteration) as error:
    print(f"Preflight failed: {error}", file=sys.stderr)
    sys.exit(1)
