package com.streamforge.dashboard;
import io.quarkus.security.identity.SecurityIdentity;
import jakarta.ws.rs.*;
import jakarta.ws.rs.container.ContainerRequestContext;
import jakarta.ws.rs.core.UriInfo;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
class AccessTest {
    ContainerRequestContext request(String path,String method) {
        var r=mock(ContainerRequestContext.class);var u=mock(UriInfo.class);
        when(r.getUriInfo()).thenReturn(u);when(u.getPath()).thenReturn(path);when(r.getMethod()).thenReturn(method);return r;
    }
    Access filter() { var f=new Access();f.enabled=true;f.identity=mock(SecurityIdentity.class);return f; }
    @Test void rejectsAnonymousWithEitherPathForm() {
        var f=filter();when(f.identity.isAnonymous()).thenReturn(true);
        assertThrows(NotAuthorizedException.class,()->f.filter(request("/api/orders","GET")));
        assertThrows(NotAuthorizedException.class,()->f.filter(request("api/orders","GET")));
        assertDoesNotThrow(()->f.filter(request("/auth/config","GET")));
    }
    @Test void viewerCannotMutateAndUnassignedUsersCannotRead() {
        var f=filter();assertThrows(ForbiddenException.class,()->f.filter(request("/api/orders","GET")));
        when(f.identity.hasRole("streamforge-viewer")).thenReturn(true);
        assertDoesNotThrow(()->f.filter(request("/api/orders","GET")));
        assertThrows(ForbiddenException.class,()->f.filter(request("/api/orders","POST")));
        assertThrows(ForbiddenException.class,()->f.filter(request("/api/orders/1/status","PATCH")));
        when(f.identity.hasRole("streamforge-operator")).thenReturn(true);
        assertDoesNotThrow(()->f.filter(request("/api/orders/1/status","PATCH")));
    }
}
