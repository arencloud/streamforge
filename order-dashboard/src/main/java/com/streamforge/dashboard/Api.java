package com.streamforge.dashboard;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.*;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

@Path("/api") @Produces(MediaType.APPLICATION_JSON) @Consumes(MediaType.APPLICATION_JSON)
public class Api {
    @Inject Orders orders;
    @Inject Archives archives;
    @ConfigProperty(name="streamforge.preview") boolean preview;
    public record Create(Long id,String customerName,BigDecimal amount) {}
    public record Change(String status,Instant expectedUpdatedAt) {}
    public record View(Order order,List<String> nextStatuses,List<Archives.Delivery> delivery) {}
    @GET @Path("/orders") public Response list() {
        try { return Response.ok(Map.of("preview",preview,"serverTime",Instant.now(),"orders",orders.list().stream().map(o->new View(o,o.nextStatuses(),archives.delivery(o))).toList())).build(); }
        catch(Exception e) { return failure(e); }
    }
    @POST @Path("/orders") public Response create(Create input,@HeaderParam("X-Streamforge-Action") String action) {
        try {
            guard(action);
            if(input==null||input.id()==null) throw new IllegalArgumentException("Order ID is required.");
            return Response.status(201).entity(orders.create(input.id(),input.customerName(),input.amount())).build();
        } catch(Exception e) { return failure(e); }
    }
    @PATCH @Path("/orders/{id}/status") public Response update(@PathParam("id") long id,Change input,@HeaderParam("X-Streamforge-Action") String action) {
        try { guard(action); if(input==null) throw new IllegalArgumentException("Status is required."); return Response.ok(orders.update(id,input.status(),input.expectedUpdatedAt())).build(); }
        catch(Exception e) { return failure(e); }
    }
    static void guard(String action) { if(!"orders".equals(action)) throw new ForbiddenException(); }
    static Response failure(Exception e) {
        int status=503; String message="Database unavailable. Try again shortly.";
        if(e instanceof IllegalArgumentException) { status=400; message=e.getMessage(); }
        else if(e instanceof Order.Conflict) { status=409; message=e.getMessage(); }
        else if(e instanceof NoSuchElementException) { status=404; message="Order not found."; }
        else if(e instanceof ForbiddenException) { status=403; message="Action header required."; }
        return Response.status(status).entity(Map.of("error",message)).build();
    }
}
