package com.streamforge.dashboard;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import java.util.Map;
@Path("/auth/config") @Produces(MediaType.APPLICATION_JSON)
public class AuthConfig {
    @ConfigProperty(name="streamforge.auth.enabled") boolean enabled;
    @ConfigProperty(name="streamforge.auth.url") String url;
    @ConfigProperty(name="streamforge.auth.realm") String realm;
    @ConfigProperty(name="streamforge.auth.client-id") String client;
    @GET public Map<String,Object> config() { return Map.of("enabled",enabled,"url",url,"realm",realm,"clientId",client); }
}
