package com.streamforge.s3;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.camel.CamelExecutionException;
import org.apache.camel.builder.AdviceWith;
import org.apache.camel.Processor;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.apache.camel.component.aws2.s3.AWS2S3Constants;
import org.apache.camel.component.kafka.KafkaConstants;
import org.apache.camel.component.kafka.consumer.KafkaManualCommit;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ArchiveRecordTest {
    private DefaultCamelContext route(Processor s3Write) throws Exception {
        var context = new DefaultCamelContext();
        var route = new S3Route();
        route.topic = "sf.public.orders";
        route.bucket = "test-bucket";
        route.prefix = "camel/";
        route.metrics = new SimpleMeterRegistry();
        context.addRoutes(route);
        AdviceWith.adviceWith(context, "kafka-to-s3", false, advice -> {
            advice.replaceFromWith("direct:test");
            advice.weaveByToUri("aws2-s3:*").replace().process(s3Write);
        });
        context.start();
        return context;
    }
    private Map<String, Object> headers(KafkaManualCommit commit) {
        return Map.of(KafkaConstants.TOPIC, "sf.public.orders", KafkaConstants.PARTITION, 2,
                KafkaConstants.OFFSET, 42L, KafkaConstants.KEY, "{\"id\":7}",
                KafkaConstants.MANUAL_COMMIT, commit);
    }

    @Test void successfulWritePrecedesCommitAndPreservesDeleteEnvelope() throws Exception {
        KafkaManualCommit commit = mock(KafkaManualCommit.class);
        AtomicReference<byte[]> body = new AtomicReference<>();
        AtomicReference<String> key = new AtomicReference<>();
        try (var context = route(e -> {
            verifyNoInteractions(commit);
            body.set(e.getMessage().getBody(byte[].class));
            key.set(e.getMessage().getHeader(AWS2S3Constants.KEY, String.class));
        })) {
            context.createProducerTemplate().requestBodyAndHeaders("direct:test",
                    "{\"op\":\"d\",\"before\":{\"id\":7},\"after\":null}", headers(commit));
        }
        verify(commit).commit();
        assertEquals("camel/sf.public.orders/2/42.json", key.get());
        var json = new ObjectMapper().readTree(body.get());
        assertEquals("d", json.path("value").path("op").asText());
        assertTrue(json.path("value").path("after").isNull());
        assertEquals(7, json.path("key").path("id").asInt());
    }

    @Test void failedS3WriteNeverCommits() throws Exception {
        KafkaManualCommit commit = mock(KafkaManualCommit.class);
        AtomicInteger attempts = new AtomicInteger();
        try (var context = route(e -> {
            attempts.incrementAndGet();
            throw new IllegalStateException("simulated S3 outage");
        })) {
            assertThrows(CamelExecutionException.class, () -> context.createProducerTemplate()
                    .requestBodyAndHeaders("direct:test", "{\"op\":\"c\"}", headers(commit)));
        }
        verifyNoInteractions(commit);
        assertEquals(3, attempts.get());
    }

    @Test void transientFailureRetriesThenCommitsOnce() throws Exception {
        KafkaManualCommit commit = mock(KafkaManualCommit.class);
        AtomicInteger attempts = new AtomicInteger();
        try (var context = route(e -> {
            verifyNoInteractions(commit);
            if (attempts.incrementAndGet() < 2) throw new IllegalStateException("temporary outage");
        })) {
            context.createProducerTemplate().requestBodyAndHeaders("direct:test", "{\"op\":\"c\"}", headers(commit));
        }
        assertEquals(2, attempts.get());
        verify(commit, times(1)).commit();
    }

    @Test void jaasEscapesSpecialCharactersAndRejectsNewlines() {
        assertEquals("\"a\\\"b\\\\c\"", Clients.jaasQuote("a\"b\\c"));
        assertThrows(IllegalArgumentException.class, () -> Clients.jaasQuote("invalid\nsecret"));
    }
}
