#!/usr/bin/env bash
set -euo pipefail
umask 077
# Aiven's AWS SDK uses JSSE trust, separately from Connect's Kafka truststore.
# Called by the original Connect entrypoint AFTER its /tmp cleanup.
# Import every PEM in the bundle, retaining public roots for public S3 endpoints.
trust_dir=$(mktemp -d /tmp/s3-trust.XXXXXX)
# The Red Hat Kafka image exposes java on PATH without necessarily setting JAVA_HOME.
java_home="${JAVA_HOME:-}"
if [[ -z "$java_home" ]]; then
  java_binary=$(readlink -f "$(command -v java)")
  java_home=$(dirname "$(dirname "$java_binary")")
fi
cp "$java_home/lib/security/cacerts" "$trust_dir/cacerts"
chmod u+w "$trust_dir/cacerts"
awk -v dir="$trust_dir" '/-----BEGIN CERTIFICATE-----/ {n++; file=dir "/ca-" n ".pem"} file {print > file} /-----END CERTIFICATE-----/ {close(file); file=""}' /mnt/s3-ca/ca.crt
for cert in "$trust_dir"/ca-*.pem; do
  test -f "$cert"
  keytool -importcert -noprompt -alias "streamforge-$(basename "$cert")" -file "$cert" \
    -keystore "$trust_dir/cacerts" -storepass changeit >/dev/null 2>&1
done
# changeit protects a truststore containing public certificates, not a private key.
export KAFKA_OPTS="${KAFKA_OPTS:-} -Djavax.net.ssl.trustStore=$trust_dir/cacerts -Djavax.net.ssl.trustStorePassword=changeit"
exec /opt/kafka/kafka_connect_mm2_shared_run.upstream.sh "$@"
