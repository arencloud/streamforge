# syntax=docker/dockerfile:1
# Pinned Red Hat Kafka runtime; qualify against your operator-supported image mapping.
ARG KAFKA_BASE=registry.redhat.io/amq-streams/kafka-42-rhel9@sha256:15d9d194de6c7509848d1e18896c6ee3d16029013675049587bd3e38c7a98b6b
# Plugin archives are architecture-independent; extract with the builder's native JVM.
FROM --platform=$BUILDPLATFORM registry.access.redhat.com/ubi9/openjdk-21@sha256:668700248b0abc5cf6d06948c32b6670557ffac39dfe4ea93ab889313453ac39 AS plugin-base
USER 0
RUN mkdir -p /plugins && chmod 755 /plugins
WORKDIR /plugins

FROM plugin-base AS debezium-plugin
ARG DEBEZIUM_VERSION=3.6.3.Final-redhat-00009
ARG DEBEZIUM_SHA512=e7b1813e79443c9bb2cddd6c2faaa0deb61a2b054598b5f2da6ede2d89dbee1a6edd15f8b6e41519f504ee3d1a4b6aef38debf49d0bd02fde57ca903f5b8531a
RUN curl --fail --location --retry 3 "https://maven.repository.redhat.com/ga/io/debezium/debezium-connector-postgres/${DEBEZIUM_VERSION}/debezium-connector-postgres-${DEBEZIUM_VERSION}-plugin.zip" -o /tmp/plugin.zip \
    && echo "${DEBEZIUM_SHA512}  /tmp/plugin.zip" | sha512sum -c - \
    && jar xf /tmp/plugin.zip && rm /tmp/plugin.zip && chmod -R a+rX /plugins

FROM plugin-base AS aiven-plugin
ARG AIVEN_VERSION=3.4.4
ARG AIVEN_SHA512=34335cd4081d6df895377850e0bdbb5e392ddb6ae7ea0381d2d7fa6549038173e98b57c56de0c53c3d06c841903c20f7d09aef93e4238c15bbd7cda7fe3839ce
RUN curl --fail --location --retry 3 "https://github.com/Aiven-Open/cloud-storage-connectors-for-apache-kafka/releases/download/v${AIVEN_VERSION}/s3-sink-connector-for-apache-kafka-${AIVEN_VERSION}.zip" -o /tmp/plugin.zip \
    && echo "${AIVEN_SHA512}  /tmp/plugin.zip" | sha512sum -c - \
    && jar xf /tmp/plugin.zip && rm /tmp/plugin.zip && chmod -R a+rX /plugins

FROM ${KAFKA_BASE} AS source
USER 0
COPY --from=debezium-plugin /plugins/ /opt/kafka/plugins/debezium/
USER 1001

FROM ${KAFKA_BASE} AS camel-connect
USER 0
COPY camel-connect/target/camel-connect-s3-0.1.0.jar /opt/kafka/plugins/streamforge-camel/
COPY camel-connect/target/lib/ /opt/kafka/plugins/streamforge-camel/
RUN chmod -R a+rX /opt/kafka/plugins/streamforge-camel
USER 1001

FROM ${KAFKA_BASE} AS aiven
USER 0
COPY --from=aiven-plugin /plugins/ /opt/kafka/plugins/aiven/
# The outer entrypoint clears /tmp. Build S3 trust only after that cleanup.
RUN mv /opt/kafka/kafka_connect_mm2_shared_run.sh /opt/kafka/kafka_connect_mm2_shared_run.upstream.sh
COPY --chmod=0755 connect/with-s3-trust.sh /opt/kafka/kafka_connect_mm2_shared_run.sh
USER 1001
