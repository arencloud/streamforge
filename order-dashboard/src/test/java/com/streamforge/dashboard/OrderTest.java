package com.streamforge.dashboard;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.Instant;
import static org.junit.jupiter.api.Assertions.*;
class OrderTest {
    final Instant time=Instant.parse("2026-01-01T00:00:00Z");
    @Test void lifecycleAndOptimisticLock() {
        var o=new Order(1,"Synthetic",new BigDecimal("10.00"),"created",time);
        assertEquals("paid",o.transition("paid",time,time.plusSeconds(1)).status());
        assertThrows(IllegalArgumentException.class,()->o.transition("shipped",time,time));
        assertThrows(Order.Conflict.class,()->o.transition("paid",time.minusSeconds(1),time));
        assertTrue(o.transition("cancelled",time,time).nextStatuses().isEmpty());
    }
    @Test void validatesMoneyAndIds() {
        assertThrows(IllegalArgumentException.class,()->Order.validate(1,"Demo",new BigDecimal("0")));
        assertThrows(IllegalArgumentException.class,()->Order.validate(1,"Demo",new BigDecimal("1.001")));
        assertThrows(IllegalArgumentException.class,()->Order.validate(Long.MAX_VALUE,"Demo",BigDecimal.ONE));
        assertThrows(IllegalArgumentException.class,()->Order.validate(1,"\n",BigDecimal.ONE));
        assertDoesNotThrow(()->Order.validate(123,"Synthetic Customer",new BigDecimal("12.50")));
    }
}
