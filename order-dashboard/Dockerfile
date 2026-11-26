ARG JAVA_RUNTIME=registry.access.redhat.com/ubi9/openjdk-21-runtime@sha256:14e5af876865b25abdc15c137dd30e68b3394aaee18e26bd1777036a52a907c5
FROM ${JAVA_RUNTIME}
WORKDIR /deployments
COPY --chown=185:0 target/quarkus-app/lib/ ./lib/
COPY --chown=185:0 target/quarkus-app/*.jar ./
COPY --chown=185:0 target/quarkus-app/app/ ./app/
COPY --chown=185:0 target/quarkus-app/quarkus/ ./quarkus/
USER 185
EXPOSE 8080
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=65", "-Djava.io.tmpdir=/tmp", "-jar", "/deployments/quarkus-run.jar"]
