package com.streamforge.connect;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.connect.data.Schema;
import org.apache.kafka.connect.errors.DataException;
import org.apache.kafka.connect.errors.RetriableException;
import org.apache.kafka.connect.sink.SinkRecord;
import org.apache.kafka.connect.sink.SinkTaskContext;
import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.apache.kafka.common.config.AbstractConfig;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectResponse;
import software.amazon.awssdk.services.s3.model.S3Exception;
import software.amazon.awssdk.core.sync.RequestBody;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class CamelS3SinkTaskTest {
    @Test void realCamelProducerPropagatesStorageFailureAndUsesStableKey() {
        var s3 = mock(S3Client.class);
        when(s3.putObject(any(PutObjectRequest.class), any(RequestBody.class)))
                .thenReturn(PutObjectResponse.builder().eTag("test").build())
                .thenThrow(S3Exception.builder().statusCode(503).message("test outage").build());
        var task = new CamelS3SinkTask() {
            @Override protected S3Client createClient(AbstractConfig config) { return s3; }
        };
        task.start(Map.of("s3.endpoint", "https://s3.example.invalid", "s3.region", "us-east-1", "s3.bucket", "test-bucket"));
        try {
            task.put(List.of(record(1, "{\"op\":\"c\"}")));
            assertThrows(RetriableException.class, () -> task.put(List.of(record(1, "{\"op\":\"c\"}"))));
            verify(s3, times(2)).putObject(argThat((PutObjectRequest r) ->
                    r.key().equals("camel-connect/sf.public.orders/1/1.json") && r.bucket().equals("test-bucket")), any(RequestBody.class));
        } finally {
            task.stop();
        }
        verify(s3).close();
    }
    SinkRecord record(long offset, String value) {
        return new SinkRecord("sf.public.orders", 1, Schema.STRING_SCHEMA, "{\"id\":7}",
                Schema.OPTIONAL_STRING_SCHEMA, value, offset);
    }

    @Test void partialBatchFailureIsRetriableAndReplayUsesIdenticalKeys() {
        var writes = new ArrayList<String>();
        var task = new CamelS3SinkTask() {
            boolean fail = true;
            @Override protected void write(String key, byte[] body) {
                writes.add(key);
                if (key.endsWith("/11.json") && fail) { fail = false; throw new RuntimeException(); }
            }
        };
        SinkTaskContext context = mock(SinkTaskContext.class);
        task.initialize(context);
        var batch = List.of(record(10, "{\"op\":\"c\"}"), record(11, "{\"op\":\"u\"}"), record(12, "{\"op\":\"d\"}"));
        assertThrows(RetriableException.class, () -> task.put(batch));
        assertEquals(2, writes.size()); // No later record was accepted after failure.
        verify(context).timeout(longThat(delay -> delay >= 500 && delay <= 1000));
        task.put(batch);
        assertEquals(writes.get(0), writes.get(2));
        assertEquals(writes.get(1), writes.get(3));
        verify(context, never()).requestCommit();
    }

    @Test void envelopePreservesDeleteAndNullTombstone() throws Exception {
        var json = new ObjectMapper();
        var deletion = json.readTree(CamelS3SinkTask.encode(record(10, "{\"op\":\"d\",\"after\":null,\"before\":{\"id\":7}}")));
        assertEquals("d", deletion.path("value").path("op").asText());
        assertTrue(deletion.path("value").path("after").isNull());
        assertTrue(json.readTree(CamelS3SinkTask.encode(record(11, null))).path("value").isNull());
    }

    @Test void invalidJsonIsRejectedWithoutWriting() {
        var task = spy(new CamelS3SinkTask());
        assertThrows(DataException.class, () -> task.put(List.of(record(0, "invalid-json"))));
        verify(task, never()).write(anyString(), any());
    }

    @Test void objectIdentityIncludesTopicPartitionAndOffset() {
        assertEquals("camel-connect/sf.public.orders/1/10.json", CamelS3SinkTask.objectKey("camel-connect/", record(10, null)));
    }

    @Test void retryBackoffIsBoundedAndGrows() {
        for (int i = 0; i < 100; i++) {
            assertTrue(CamelS3SinkTask.retryDelay(1) <= 1000);
            long delay = CamelS3SinkTask.retryDelay(100);
            assertTrue(delay >= 15000 && delay <= 30000);
        }
    }
}
