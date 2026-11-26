package com.streamforge.s3;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.camel.Exchange;
import org.apache.camel.component.aws2.s3.AWS2S3Constants;
import org.apache.camel.component.kafka.KafkaConstants;
import org.apache.camel.component.kafka.consumer.KafkaManualCommit;

import java.util.LinkedHashMap;
import java.util.Objects;

public final class ArchiveRecord {
    private static final ObjectMapper JSON = new ObjectMapper();
    static final String COMMIT = "streamforge.commit";

    private ArchiveRecord() { }

    public static void prepare(Exchange exchange, String prefix) throws Exception {
        var message = exchange.getMessage();
        String topic = Objects.requireNonNull(message.getHeader(KafkaConstants.TOPIC, String.class));
        Integer partition = Objects.requireNonNull(message.getHeader(KafkaConstants.PARTITION, Integer.class));
        Long offset = Objects.requireNonNull(message.getHeader(KafkaConstants.OFFSET, Long.class));
        KafkaManualCommit commit = Objects.requireNonNull(
                message.getHeader(KafkaConstants.MANUAL_COMMIT, KafkaManualCommit.class));
        exchange.setProperty(COMMIT, commit);
        var record = new LinkedHashMap<String, Object>();
        record.put("topic", topic);
        record.put("partition", partition);
        record.put("offset", offset);
        record.put("timestamp", message.getHeader(KafkaConstants.TIMESTAMP));
        String key = message.getHeader(KafkaConstants.KEY, String.class);
        String value = message.getBody(String.class);
        record.put("key", key == null ? null : JSON.readTree(key));
        record.put("value", value == null ? null : JSON.readTree(value));
        message.removeHeaders("*");
        message.setHeader(AWS2S3Constants.KEY, prefix + topic + "/" + partition + "/" + offset + ".json");
        message.setHeader(AWS2S3Constants.CONTENT_TYPE, "application/json");
        message.setBody(JSON.writeValueAsBytes(record));
    }

    public static void commit(Exchange exchange) {
        // Remains on the Kafka consumer thread; never use an async EIP before this call.
        exchange.getProperty(COMMIT, KafkaManualCommit.class).commit();
    }
}
