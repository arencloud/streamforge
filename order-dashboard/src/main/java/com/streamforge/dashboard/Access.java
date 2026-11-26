package com.streamforge.dashboard;

import io.quarkus.security.identity.SecurityIdentity;
import jakarta.annotation.Priority;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.container.*;
import jakarta.ws.rs.ext.Provider;
import org.eclipse.microprofile.config.inject.ConfigProperty;

@Provider @Priority(Priorities.AUTHORIZATION)
public class Access implements ContainerRequestFilter {
    @Inject SecurityIdentity identity;
    @ConfigProperty(name="streamforge.auth.enabled") boolean enabled;
    @Override public void filter(ContainerRequestContext request) {
        String path=request.getUriInfo().getPath().replaceFirst("^/+", "");
        if(!enabled || !(path.equals("api") || path.startsWith("api/"))) return;
        if(identity.isAnonymous()) throw new NotAuthorizedException("Bearer");
        boolean operator=identity.hasRole("streamforge-operator");
        boolean reader=operator || identity.hasRole("streamforge-viewer");
        if(!reader || (!request.getMethod().equals("GET") && !operator)) throw new ForbiddenException();
    }
}
