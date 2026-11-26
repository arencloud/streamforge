package com.streamforge.dashboard;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
class ArchiveEventTest {
    final ObjectMapper json=new ObjectMapper();
    final Instant time=Instant.parse("2026-01-01T00:00:00.123456Z");
    String envelope="{\"op\":\"u\",\"after\":{\"id\":42,\"status\":\"paid\",\"updated_at\":\"2026-01-01T00:00:00.123456Z\"}}";
    @Test void readsAllSinkFormatsWithoutConfusingOldVersions() throws Exception {
        var a=ArchiveEvent.parse(json,json.writeValueAsString(Map.of("value",envelope)),"aiven/x.jsonl",time);
        var b=ArchiveEvent.parse(json,"{\"value\":"+envelope+"}","camel/x.json",time);
        var c=ArchiveEvent.parse(json,"{\"value\":"+envelope+"}","camel-connect/x.json",time);
        var order=new Order(42,"Synthetic",BigDecimal.TEN,"paid",time);
        assertTrue(a.matches(order)); assertTrue(b.matches(order)); assertTrue(c.matches(order));
        assertFalse(a.matches(new Order(42,"Synthetic",BigDecimal.TEN,"paid",time.plusNanos(1000))));
        assertFalse(a.matches(new Order(42,"Synthetic",BigDecimal.TEN,"shipped",time)));
    }
    @Test void tombstonesAndDeletesAreNotCurrentState() throws Exception {
        assertNull(ArchiveEvent.parse(json,"{\"value\":null}","x",time));
        assertNull(ArchiveEvent.parse(json,"{\"value\":{\"op\":\"d\",\"after\":null}}","x",time));
    }
}
