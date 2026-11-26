package com.streamforge.s3;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import io.micrometer.core.instrument.MeterRegistry;
import org.apache.camel.builder.RouteBuilder;
import org.eclipse.microprofile.config.inject.ConfigProperty;

@ApplicationScoped
public class S3Route extends RouteBuilder {
    @ConfigProperty(name = "streamforge.kafka.topic") String topic;
    @ConfigProperty(name = "streamforge.s3.bucket") String bucket;
    @ConfigProperty(name = "streamforge.s3.prefix") String prefix;
    @Inject MeterRegistry metrics;

    @Override public void configure() {
        // Fail the exchange, so the Kafka SyncCommitManager seeks back to this record.
        onException(Exception.class)
                .maximumRedeliveries(2).redeliveryDelay(1000)
                .useExponentialBackOff().backOffMultiplier(2).maximumRedeliveryDelay(10000)
                .useCollisionAvoidance()
                .logExhausted(false).logRetryAttempted(false)
                .process(e -> metrics.counter("streamforge.s3.failures").increment())
                .handled(false);

        from("kafka:" + topic + "?groupId=camel-s3")
                .routeId("kafka-to-s3")
                .process(e -> ArchiveRecord.prepare(e, prefix))
                .to("aws2-s3:" + bucket + "?amazonS3Client=#s3Client&autoCreateBucket=false&lazyStartProducer=true")
                .process(ArchiveRecord::commit)
                .process(e -> metrics.counter("streamforge.s3.records").increment());
    }
}
