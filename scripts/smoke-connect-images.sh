#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
smoke_dir=$(mktemp -d)
trap 'rm -rf "$smoke_dir"' EXIT
chmod 755 "$smoke_dir"
image_prefix=${IMAGE_PREFIX:-streamforge/}
image_tag=${IMAGE_TAG:-test}
IFS=',' read -r -a platforms <<< "${PLATFORMS:-linux/amd64}"
components=("$@")
if [[ ${#components[@]} -eq 0 ]]; then components=(debezium aiven camel); fi
"${JAVA_HOME:?Set JAVA_HOME to a JDK 17 or newer}/bin/javac" --release 17 -d "$smoke_dir" connect/tests/PluginSmoke.java
for component in "${components[@]}"; do
  case "$component" in
    debezium) connector=io.debezium.connector.postgresql.PostgresConnector ;;
    aiven) connector=io.aiven.kafka.connect.s3.AivenKafkaConnectS3SinkConnector ;;
    camel) connector=com.streamforge.connect.CamelS3SinkConnector ;;
    *) echo "Unknown component: $component" >&2; exit 1 ;;
  esac
  for platform in "${platforms[@]}"; do
    echo "Checking $component on $platform"
    docker run --rm --platform "$platform" --network none --user 1000690000:0 \
    --mount "type=bind,source=$smoke_dir,target=/smoke,readonly" \
    --entrypoint java "${image_prefix}connect-${component}:${image_tag}" \
    -cp '/opt/kafka/libs/*:/smoke' PluginSmoke "$connector"
  done
done
