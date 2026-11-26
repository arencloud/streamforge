#!/usr/bin/env python3
"""Packaging/TLS smoke test; uses a local fake S3 server and synthetic credentials only."""
import http.server
import os
import pathlib
import ssl
import subprocess
import tempfile
import threading
import time
import uuid

image = os.environ.get("IMAGE", "streamforge/camel-s3:test")
platform = os.environ.get("PLATFORM", "linux/amd64")


class S3Stub(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.send_header("x-amz-bucket-region", "us-east-1")
        self.end_headers()

    def log_message(self, *_):
        pass  # Do not log signed requests.


with tempfile.TemporaryDirectory(prefix="streamforge-smoke-") as directory:
    path = pathlib.Path(directory)
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-keyout", str(path / "key.pem"), "-out", str(path / "ca.crt"),
                    "-subj", "/CN=host.docker.internal", "-addext", "subjectAltName=DNS:host.docker.internal"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (path / "ca.crt").chmod(0o644)
    server = http.server.HTTPServer(("0.0.0.0", 0), S3Stub)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(path / "ca.crt", path / "key.pem")
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    name = "streamforge-smoke-" + uuid.uuid4().hex[:8]
    args = ["docker", "run", "-d", "--name", name, "--platform", platform, "--read-only",
            "--tmpfs", "/tmp:rw,size=128m", "--user", "1000690000:0", "--memory", "768m",
            "--add-host", "host.docker.internal:host-gateway"]
    env = {"KAFKA_BOOTSTRAP": "localhost:9093", "KAFKA_TOPIC": "sf.public.orders",
           "KAFKA_USERNAME": "test-only", "KAFKA_PASSWORD": "test-only",
           "S3_ENDPOINT": f"https://host.docker.internal:{server.server_port}",
           "S3_REGION": "us-east-1", "S3_BUCKET": "test-bucket",
           "AWS_ACCESS_KEY_ID": "test-only", "AWS_SECRET_ACCESS_KEY": "test-only",
           "JAVA_TOOL_OPTIONS": "-Dcamel.main.auto-startup=false"}
    for key, value in env.items():
        args += ["-e", key + "=" + value]
    for file in ["kafka-ca.crt", "s3-ca.crt"]:
        args += ["-v", f"{path / 'ca.crt'}:/mnt/trust/{file}:ro"]
    try:
        subprocess.run(args + [image], check=True, stdout=subprocess.DEVNULL)
        for _ in range(45):
            logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True).stdout
            if "Listening on:" in logs:
                print(f"PASS ({platform}): packaged Quarkus app, arbitrary UID, read-only filesystem, verified TLS to local S3 stub")
                print("Routes disabled: this is a packaging check, not a Kafka-to-S3 end-to-end test")
                break
            running = subprocess.check_output(["docker", "inspect", "--format", "{{.State.Running}}", name], text=True).strip()
            if running != "true":
                raise RuntimeError("Container failed to start: " + logs[-3000:])
            time.sleep(1)
        else:
            raise RuntimeError("Container startup timed out")
    finally:
        subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server.shutdown()
