package com.streamforge.dashboard;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;

public record ArchiveEvent(long orderId, String status, Instant rowVersion, String operation, String objectKey, Instant observedAt) {
    public boolean matches(Order order) { return order.id()==orderId && order.status().equals(status) && order.updatedAt().equals(rowVersion); }
    static ArchiveEvent parse(ObjectMapper json, String line, String key, Instant observed) throws Exception {
        JsonNode envelope=json.readTree(line).path("value");
        if(envelope.isTextual()) envelope=json.readTree(envelope.textValue());
        if(envelope.has("payload")) envelope=envelope.path("payload");
        JsonNode row=envelope.path("after");
        if(!row.isObject() || !row.has("id") || !row.has("updated_at")) return null;
        JsonNode time=row.path("updated_at");
        // The current PostgreSQL column is timestamptz: Debezium emits an ISO UTC string.
        // Also accept MicroTimestamp values for fixtures/compatible schemas.
        Instant version=time.isNumber()?Instant.ofEpochSecond(time.longValue()/1_000_000,(time.longValue()%1_000_000)*1000):Instant.parse(time.asText());
        return new ArchiveEvent(row.path("id").asLong(),row.path("status").asText(),version,envelope.path("op").asText(),key,observed);
    }
}
