package com.streamforge.dashboard;

import io.agroal.api.AgroalDataSource;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.enterprise.inject.Instance;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import java.math.BigDecimal;
import java.sql.*;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;

@ApplicationScoped
public class Orders {
    @Inject Instance<AgroalDataSource> db;
    @ConfigProperty(name="streamforge.preview") boolean preview;
    private final Map<Long,Order> memory = new LinkedHashMap<>();
    private boolean seeded;
    private void seed() {
        if (!seeded) {
            seeded = true;
            memory.put(910010L, new Order(910010, "Northwind Studio", new BigDecimal("149.00"), "created", Instant.now().minusSeconds(240)));
            memory.put(910011L, new Order(910011, "Atlas Workshop", new BigDecimal("85.50"), "paid", Instant.now().minusSeconds(120)));
            memory.put(910012L, new Order(910012, "Cedar & Co.", new BigDecimal("320.00"), "shipped", Instant.now().minusSeconds(60)));
        }
    }
    public synchronized List<Order> list() throws SQLException {
        if (preview) { seed(); return memory.values().stream().sorted(Comparator.comparing(Order::updatedAt).reversed()).limit(100).toList(); }
        try (var c=db.get().getConnection(); var s=c.prepareStatement("SELECT id, customer_name, amount, status, updated_at FROM public.orders ORDER BY updated_at DESC, id DESC LIMIT 100")) {
            s.setQueryTimeout(5);
            try (var r=s.executeQuery()) { var out=new ArrayList<Order>(); while(r.next()) out.add(row(r)); return out; }
        }
    }
    public synchronized Order create(long id, String customer, BigDecimal amount) throws SQLException {
        Order.validate(id, customer, amount);
        if (preview) {
            seed(); if(memory.containsKey(id)) throw new Order.Conflict("Order ID already exists.");
            if(memory.size()>=1000) throw new Order.Conflict("Preview is full. Restart it to reset.");
            var order=new Order(id,customer.strip(),amount,"created",Instant.now().truncatedTo(ChronoUnit.MICROS)); memory.put(id,order); return order;
        }
        try (var c=db.get().getConnection(); var s=c.prepareStatement("INSERT INTO public.orders(id,customer_name,amount,status,updated_at) VALUES (?,?,?,'created',clock_timestamp()) RETURNING id,customer_name,amount,status,updated_at")) {
            s.setQueryTimeout(5); s.setLong(1,id); s.setString(2,customer.strip()); s.setBigDecimal(3,amount);
            try(var r=s.executeQuery()) { r.next(); return row(r); }
        } catch(SQLException e) { if("23505".equals(e.getSQLState())) throw new Order.Conflict("Order ID already exists."); throw e; }
    }
    public synchronized Order update(long id,String next,Instant expected) throws SQLException {
        if(expected==null || next==null) throw new IllegalArgumentException("Status and expectedUpdatedAt are required.");
        if(preview) {
            seed(); var old=memory.get(id); if(old==null) throw new NoSuchElementException();
            var order=old.transition(next,expected,Instant.now().truncatedTo(ChronoUnit.MICROS)); memory.put(id,order); return order;
        }
        try(var c=db.get().getConnection()) {
            c.setAutoCommit(false);
            try {
                Order old;
                try(var s=c.prepareStatement("SELECT id,customer_name,amount,status,updated_at FROM public.orders WHERE id=? FOR UPDATE")) {
                    s.setQueryTimeout(5); s.setLong(1,id); try(var r=s.executeQuery()) { if(!r.next()) throw new NoSuchElementException(); old=row(r); }
                }
                old.transition(next,expected,Instant.now());
                try(var s=c.prepareStatement("UPDATE public.orders SET status=?,updated_at=clock_timestamp() WHERE id=? RETURNING id,customer_name,amount,status,updated_at")) {
                    s.setQueryTimeout(5); s.setString(1,next); s.setLong(2,id); try(var r=s.executeQuery()) { r.next(); var order=row(r); c.commit(); return order; }
                }
            } catch(SQLException|RuntimeException e) { c.rollback(); throw e; }
        }
    }
    static Order row(ResultSet r) throws SQLException { return new Order(r.getLong(1),r.getString(2),r.getBigDecimal(3),r.getString(4),r.getTimestamp(5).toInstant()); }
}
