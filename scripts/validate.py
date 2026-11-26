#!/usr/bin/env python3
"""Render all supported modes; check security and integration invariants without credentials."""
import argparse
import ipaddress
import pathlib
import re
import subprocess
import sys
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def render(mode, files):
    cmd = ["helm", "template", "streamforge", str(ROOT / "charts/streamforge"), "-n", "streamforge"]
    for file in files:
        cmd += ["-f", file]
    cmd += ["--set", "mode=" + mode]
    return [d for d in yaml.safe_load_all(subprocess.check_output(cmd, text=True)) if d]


def check(docs, mode, production=False):
    kinds = {}
    for doc in docs:
        key = (doc["kind"], doc["metadata"]["name"])
        assert key not in kinds, f"duplicate resource {key}"
        kinds[key] = doc
        assert doc["kind"] != "Secret", "Git must contain secret references only"
    assert kinds[("Certificate", "kafka-listener")]["spec"]["privateKey"]["encoding"] == "PKCS8", "Kafka PEM keys require PKCS8 encoding"
    kafka = next(d for d in docs if d["kind"] == "Kafka")["spec"]["kafka"]
    assert all(l["tls"] and l["authentication"]["type"] == "scram-sha-512" for l in kafka["listeners"])
    assert kafka["config"]["min.insync.replicas"] == 2
    assert kafka["config"]["unclean.leader.election.enable"] is False
    assert all(l["type"] == "internal" for l in kafka["listeners"]), "Retain native Streams listeners"
    assert "istio.io/use-waypoint" not in yaml.safe_dump(kafka), "Kafka must not use a waypoint"
    namespace = next(d for d in docs if d["kind"] == "Namespace")
    labels = namespace["metadata"]["labels"]
    assert "istio.io/use-waypoint" not in labels, "Namespace-wide waypoints would capture Kafka"
    mesh_enabled = labels.get("istio.io/dataplane-mode") == "ambient"
    if production:
        assert mesh_enabled, "Production profile requires ambient mTLS"
    if mesh_enabled:
        assert len(labels) >= 4, "Mesh discovery label required"
        assert kinds[("PeerAuthentication", "streamforge-strict")]["spec"] == {"mtls": {"mode": "STRICT"}}
        assert kinds[("AuthorizationPolicy", "streamforge-default-deny")]["spec"] == {}
        gateways = [d for d in docs if d["kind"] == "Gateway"]
        assert len(gateways) == 1
        gateway = gateways[0]
        assert gateway["spec"]["gatewayClassName"] == "istio-waypoint"
        assert gateway["metadata"]["labels"]["istio.io/waypoint-for"] == "all", "REST pod forwarding needs workload routing"
        assert gateway["spec"]["listeners"][0]["protocol"] == "HBONE"
        waypoint = gateway["metadata"]["name"]
        waypoint_policy = kinds[("AuthorizationPolicy", "streamforge-waypoint-clients")]["spec"]
        assert waypoint_policy["targetRefs"][0]["name"] == waypoint
        for rule in waypoint_policy["rules"]:
            assert rule["from"][0]["source"]["principals"], "Every waypoint allow requires authenticated identity"
            for target in rule["to"]:
                assert not {"9090", "9091", "9093"}.intersection(target["operation"]["ports"]), "No Kafka at waypoint"
        require_waypoint = kinds[("AuthorizationPolicy", "api-require-waypoint")]["spec"]
        assert require_waypoint["selector"]["matchLabels"] == {"streamforge.io/require-waypoint": "true"}
        assert all(p.endswith("/sa/" + waypoint) for p in require_waypoint["rules"][0]["from"][0]["source"]["principals"])
        options = yaml.safe_load(kinds[("ConfigMap", "streamforge-waypoint-options")]["data"]["deployment"])
        assert options["spec"]["replicas"] >= 2
        assert ("NetworkPolicy", "ambient-hbone") in kinds
        assert ("NetworkPolicy", "waypoint-control-plane") in kinds
    pools = [d for d in docs if d["kind"] == "KafkaNodePool"]
    assert len(pools) == 2 and all(d["spec"]["replicas"] == 3 for d in pools)
    assert all(d["spec"]["storage"]["deleteClaim"] is False for d in pools)
    assert all("istio.io/use-waypoint" not in yaml.safe_dump(d) for d in pools), "No broker/controller waypoint enrollment"
    assert (("KafkaConnector", "aiven-s3") in kinds) == (mode in ("aiven", "both", "all"))
    assert (("Deployment", "camel-s3") in kinds) == (mode in ("camel", "both", "all"))
    assert (("KafkaConnector", "camel-connect-s3") in kinds) == (mode in ("camel-connect", "all"))
    assert ("NetworkPolicy", "sinks-s3") not in kinds, "Do not combine all sink egress destinations"
    for sink, enabled in (
        ("aiven", mode in ("aiven", "both", "all")),
        ("camel", mode in ("camel", "both", "all")),
        ("camel-connect", mode in ("camel-connect", "all")),
    ):
        policy = kinds.get(("NetworkPolicy", sink + "-s3-egress"))
        assert bool(policy) == enabled
        if policy:
            expected_selector = {"app": "camel-s3"} if sink == "camel" else {"strimzi.io/cluster": "connect-" + sink}
            assert policy["spec"]["podSelector"] == {"matchLabels": expected_selector}
            assert policy["spec"]["egress"][0]["ports"] == [{"protocol": "TCP", "port": 443}]
            assert policy["spec"]["egress"][0]["to"], "Each sink needs explicit destinations"
    external_secrets = {d["metadata"]["name"]: d["spec"] for d in docs if d["kind"] == "ExternalSecret"}
    secret_keys = {name: {item["secretKey"] for item in spec["data"]} for name, spec in external_secrets.items()}
    expected_auth = {"source-auth": "KAFKA_SOURCE_PASSWORD", "aiven-auth": "KAFKA_AIVEN_PASSWORD",
                     "camel-auth": "KAFKA_CAMEL_QUARKUS_PASSWORD", "camel-connect-auth": "KAFKA_CAMEL_CONNECT_PASSWORD"}
    for name, prop in expected_auth.items():
        if name in external_secrets:
            assert external_secrets[name]["data"][0]["remoteRef"]["property"] == prop
    assert secret_keys["external-trust"] == {"kafka-ca.crt"}, "S3 CAs belong to each sink entry"
    assert external_secrets["external-trust"]["data"][0]["remoteRef"]["property"] == "KAFKA_CA_PEM"
    pg_secret = external_secrets["postgres-credentials"]
    assert {item["secretKey"]: item["remoteRef"]["property"] for item in pg_secret["data"]} == {
        "username": "PG_CDC_USERNAME", "password": "PG_CDC_PASSWORD", "ca.crt": "PG_CA_PEM",
        "database": "PG_DATABASE", "host": "PG_HOST", "port": "PG_PORT",
    }, "PostgreSQL must fetch only the six runtime fields"
    egress_port = kinds[("NetworkPolicy", "source-postgres")]["spec"]["egress"][0]["ports"][0]["port"]
    assert f'ne .port "{egress_port}"' in pg_secret["target"]["template"]["data"]["port"], "Runtime and egress ports must match"
    for sink in ("aiven", "camel", "camel-connect"):
        name = "s3-" + sink
        if name not in external_secrets:
            continue
        spec = external_secrets[name]
        props = {item["secretKey"]: item["remoteRef"]["property"] for item in spec["data"]}
        assert props["ca.crt"] == "S3_CA_CERTIFICATE_PEM"
        assert {props[key] for key in ("endpoint", "region", "bucket", "path-style")} == {"S3_ENDPOINT", "S3_REGION", "S3_BUCKET", "S3_PATH_STYLE"}
        template = spec["target"]["template"]
        assert template["engineVersion"] == "v2" and template["mergePolicy"] == "Merge"
        assert "ERROR_S3_ENDPOINT_REQUIRE_HTTPS" in template["data"]["endpoint"]
        if sink == "aiven":
            assert "ERROR_AIVEN_REQUIRES_S3_PATH_STYLE_TRUE" in template["data"]["path-style"]

    def check_env(env):
        for item in env:
            ref = item.get("valueFrom", {}).get("secretKeyRef")
            if ref:
                assert ref["key"] in secret_keys[ref["name"]], "Unresolved Secret key reference"
            if item["name"] in ("S3_ENDPOINT", "S3_REGION", "S3_BUCKET", "S3_PATH_STYLE", "PG_HOST", "PG_PORT", "PG_DATABASE"):
                assert ref, "External service settings must come from their Secret"

    topics = {d["spec"].get("topicName", d["metadata"]["name"]): d["spec"] for d in docs if d["kind"] == "KafkaTopic"}
    for d in docs:
        if d["kind"] == "KafkaConnect":
            s = d["spec"]
            check_env(s["template"]["connectContainer"]["env"])
            for volume in s["template"]["pod"]["volumes"]:
                secret = volume["secret"]
                assert all(item["key"] in secret_keys[secret["secretName"]] for item in secret["items"])
            if mesh_enabled:
                assert s["template"]["apiService"]["metadata"]["labels"]["istio.io/use-waypoint"] == waypoint
                assert s["template"]["pod"]["metadata"]["labels"]["streamforge.io/require-waypoint"] == "true"
                assert s["template"]["pod"]["metadata"]["labels"]["istio.io/use-waypoint"] == waypoint
            for key in ("configStorageTopic", "offsetStorageTopic", "statusStorageTopic"):
                assert s[key] in topics
                assert topics[s[key]]["config"]["cleanup.policy"] == "compact"
            assert topics[s["configStorageTopic"]]["partitions"] == 1
            assert s["config"]["connector.client.config.override.policy"] == "None"
        if d["kind"] == "KafkaTopic":
            assert d["spec"]["replicas"] == 3
        if d["kind"] == "KafkaConnector":
            assert d["spec"]["config"]["errors.tolerance"] == "none"
            for key, value in d["spec"]["config"].items():
                if isinstance(value, str) and value.startswith("${env:"):
                    env_name = value[len("${env:"):-1]
                    worker = kinds[("KafkaConnect", d["metadata"]["labels"]["strimzi.io/cluster"])]["spec"]
                    assert env_name in {e["name"] for e in worker["template"]["connectContainer"]["env"]}
                    assert re.fullmatch(worker["config"]["config.providers.env.param.allowlist.pattern"], env_name)
        if d["kind"] == "Deployment" and d["metadata"]["name"] == "camel-s3":
            pod = d["spec"]["template"]["spec"]
            check_env(pod["containers"][0]["env"])
            trust = next(v for v in pod["volumes"] if v["name"] == "trust")
            for source in trust["projected"]["sources"]:
                secret = source["secret"]
                assert all(item["key"] in secret_keys[secret["name"]] for item in secret["items"])
    for name in ("kafka-api", "connect-api"):
        api_policy = kinds[("NetworkPolicy", name)]["spec"]
        assert api_policy["podSelector"], "API egress must select only its intended workloads"
        assert api_policy["egress"][0]["to"], "API egress must use explicit destinations"
        assert {p["port"] for p in api_policy["egress"][0]["ports"]} == {443, 6443}
    source = kinds[("KafkaConnector", "postgres-orders")]["spec"]["config"]
    expected = source["topic.prefix"] + "." + source["table.include.list"].replace("\\.", ".")
    assert expected in topics, "PostgreSQL table/prefix and declared topic disagree"
    assert source["database.sslmode"] == "verify-full"
    assert source["database.hostname"] == "${env:PG_HOST}"
    assert source["database.port"] == "${env:PG_PORT}"
    assert source["database.dbname"] == "${env:PG_DATABASE}"
    assert source["database.sslrootcert"] == "/mnt/postgres-ca/ca.crt"
    if production:
        serialized = yaml.safe_dump_all(docs)
        assert "example.invalid" not in serialized and "build-required" not in serialized, "Configure endpoints and images first"
        for d in docs:
            if d["kind"] == "KafkaConnect":
                assert re.search(r"@sha256:[0-9a-f]{64}$", d["spec"]["image"]), "Pin Connect images by digest"
            if d["kind"] == "Deployment":
                for c in d["spec"]["template"]["spec"]["containers"]:
                    assert re.search(r"@sha256:[0-9a-f]{64}$", c["image"]), "Pin application images by digest"
            if d["kind"] == "NetworkPolicy":
                for rule in d["spec"].get("egress", []):
                    for peer in rule.get("to", []):
                        if "ipBlock" in peer:
                            net = ipaddress.ip_network(peer["ipBlock"]["cidr"])
                            assert net.prefixlen > 0, "Unrestricted egress is forbidden"
                            for reserved in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"):
                                r = ipaddress.ip_network(reserved)
                                assert net.version != r.version or not net.overlaps(r), "Replace documentation-only CIDRs"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--values", action="append", default=[])
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--mode", choices=["aiven", "camel", "camel-connect", "both", "all"])
    args = parser.parse_args()
    try:
        for mode in ([args.mode] if args.mode else ["aiven", "camel", "camel-connect", "both", "all"]):
            docs = render(mode, args.values)
            check(docs, mode, args.production)
            print(f"{mode}: {len(docs)} resources validated")
    except (AssertionError, subprocess.CalledProcessError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        sys.exit(1)
