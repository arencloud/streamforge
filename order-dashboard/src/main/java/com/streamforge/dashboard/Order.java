package com.streamforge.dashboard;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;

public record Order(long id, String customerName, BigDecimal amount, String status, Instant updatedAt) {
    static final Map<String, List<String>> NEXT = Map.of(
        "created", List.of("paid", "cancelled"), "paid", List.of("shipped", "cancelled"),
        "shipped", List.of("completed"), "completed", List.of(), "cancelled", List.of());
    public List<String> nextStatuses() { return NEXT.getOrDefault(status, List.of()); }
    public static void validate(long id, String customer, BigDecimal amount) {
        if (id < 1 || id > 9007199254740991L) throw new IllegalArgumentException("Invalid order ID.");
        if (customer == null || customer.isBlank() || customer.length() > 80 || customer.chars().anyMatch(Character::isISOControl))
            throw new IllegalArgumentException("Customer must contain 1–80 printable characters.");
        if (amount == null || amount.signum() <= 0 || amount.compareTo(new BigDecimal("9999999999.99")) > 0 || amount.scale() > 2)
            throw new IllegalArgumentException("Amount must be positive with at most two decimal places.");
    }
    public Order transition(String next, Instant expected, Instant now) {
        if (!updatedAt.equals(expected)) throw new Conflict("Order changed. Refresh and try again.");
        if (!nextStatuses().contains(next)) throw new IllegalArgumentException("This status transition is not allowed.");
        return new Order(id, customerName, amount, next, now);
    }
    public static class Conflict extends RuntimeException { public Conflict(String message) { super(message); } }
}
