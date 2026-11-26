package com.streamforge.dashboard;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.quarkus.scheduler.Scheduled;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import software.amazon.awssdk.auth.credentials.*;
import software.amazon.awssdk.http.apache.ApacheHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import javax.net.ssl.TrustManagerFactory;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.time.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

@ApplicationScoped
public class Archives {
    static final List<String> SINKS=List.of("aiven","camel","camel-connect");
    @Inject ObjectMapper json;
    @ConfigProperty(name="streamforge.preview") boolean preview;
    @ConfigProperty(name="streamforge.s3.root") String root;
    @ConfigProperty(name="streamforge.s3.topic") String topic;
    private final Map<String,S3Client> clients=new HashMap<>();
    private final Map<String,Snapshot> snapshots=new ConcurrentHashMap<>();
    private final Map<String,Map<String,String>> seenObjects=new HashMap<>();
    record Snapshot(String state, Instant scannedAt, boolean bounded, int objects, Map<Long,ArchiveEvent> events) {}
    public record Delivery(String sink, String state, Instant scannedAt, boolean bounded, int objects, String objectKey, Instant observedAt) {}

    public List<Delivery> delivery(Order order) {
        var out=new ArrayList<Delivery>();
        for(String name:SINKS) {
            if(preview) {
                long delay=switch(name) {case "aiven" -> 12; case "camel" -> 3; default -> 6;};
                boolean delivered=Instant.now().isAfter(order.updatedAt().plusSeconds(delay));
                out.add(new Delivery(name,delivered?"delivered":"pending",Instant.now(),false,0,null,null)); continue;
            }
            Snapshot s=snapshots.get(name);
            if(s==null) { out.add(new Delivery(name,"starting",null,false,0,null,null)); continue; }
            var event=s.events().get(order.id());
            boolean match=event!=null && event.matches(order);
            // Old observations remain visible during outages, but never masquerade as a fresh check.
            String state=!s.state().equals("ok")?s.state():(s.scannedAt().isBefore(Instant.now().minusSeconds(120))?"stale":(match?"delivered":"not-observed"));
            out.add(new Delivery(name,state,s.scannedAt(),s.bounded(),s.objects(),match?event.objectKey():null,match?event.observedAt():null));
        }
        return out;
    }
    @Scheduled(every="{streamforge.s3.scan-interval}", concurrentExecution=Scheduled.ConcurrentExecution.SKIP, delayed="2s")
    void scan() {
        if(preview) return;
        for(String name:SINKS) {
            var previous=snapshots.get(name);
            try {
                Path base=Path.of(root,name);
                if(!Files.isDirectory(base)) { snapshots.put(name,new Snapshot("unconfigured",null,false,0,Map.of())); continue; }
                S3Client client=clients.get(name);
                if(client==null) { client=client(base); clients.put(name,client); }
                String bucket=read(base,"bucket"),prefix=read(base,"prefix")+topic+"/";
                Instant deadline=Instant.now().plusSeconds(15);
                var objects=new ArrayList<S3Object>();
                String token=null;
                // This is a bounded showcase observer, not a warehouse indexer. Do not hide partial scans.
                for(int page=0;page<10;page++) {
                    var listing=client.listObjectsV2(ListObjectsV2Request.builder().bucket(bucket).prefix(prefix).maxKeys(1000).continuationToken(token).build());
                    objects.addAll(listing.contents()); token=listing.nextContinuationToken(); if(token==null || Instant.now().isAfter(deadline)) break;
                }
                objects.sort(Comparator.comparing(S3Object::lastModified).reversed());
                boolean bounded=token!=null || objects.size()>200;
                var events=new HashMap<Long,ArchiveEvent>(previous==null?Map.of():previous.events());
                var known=seenObjects.getOrDefault(name,Map.of());
                var seen=new HashMap<String,String>();
                int inspected=0;
                for(var object:objects.stream().limit(200).toList()) {
                    if(Instant.now().isAfter(deadline)) { bounded=true; break; }
                    if(!(object.key().endsWith(".json")||object.key().endsWith(".jsonl"))) continue;
                    if(object.size()>2_097_152) { bounded=true; continue; }
                    if(object.eTag()!=null && object.eTag().equals(known.get(object.key()))) { seen.put(object.key(),object.eTag()); inspected++; continue; }
                    try(var stream=client.getObject(GetObjectRequest.builder().bucket(bucket).key(object.key()).build())) {
                        byte[] bytes=stream.readNBytes(2_097_153);
                        if(bytes.length>2_097_152) { bounded=true; continue; }
                        inspected++;
                        for(String line:new String(bytes,StandardCharsets.UTF_8).split("\\R")) {
                            if(line.isBlank()) continue;
                            ArchiveEvent event=ArchiveEvent.parse(json,line,object.key(),Instant.now());
                            if(event!=null) events.merge(event.orderId(),event,(a,b)->a.rowVersion().isAfter(b.rowVersion())?a:b);
                        }
                    }
                    if(object.eTag()!=null) seen.put(object.key(),object.eTag());
                }
                if(events.size()>5000) {
                    bounded=true;
                    var latest=events.values().stream().sorted(Comparator.comparing(ArchiveEvent::rowVersion).reversed()).limit(5000).toList();
                    events.clear(); latest.forEach(event->events.put(event.orderId(),event));
                }
                seenObjects.put(name,Map.copyOf(seen));
                snapshots.put(name,new Snapshot("ok",Instant.now(),bounded,inspected,Map.copyOf(events)));
            } catch(Exception e) {
                // Exception text may contain endpoints, account identifiers, or payloads; expose only a category.
                String state=e instanceof S3Exception s && s.statusCode()==403?"access-denied":"unavailable";
                snapshots.put(name,new Snapshot(state,previous==null?null:previous.scannedAt(),previous!=null&&previous.bounded(),previous==null?0:previous.objects(),previous==null?Map.of():previous.events()));
            }
        }
    }
    static String read(Path base,String name) throws IOException { return Files.readString(base.resolve(name)).strip(); }
    static S3Client client(Path base) throws Exception {
        URI endpoint=URI.create(read(base,"endpoint"));
        if(!"https".equals(endpoint.getScheme()) || endpoint.getUserInfo()!=null || endpoint.getHost()==null || endpoint.getQuery()!=null || endpoint.getFragment()!=null)
            throw new IllegalArgumentException("S3 requires HTTPS without embedded credentials.");
        var trust=KeyStore.getInstance(KeyStore.getDefaultType()); trust.load(null,null);
        try(var in=Files.newInputStream(base.resolve("ca.crt"))) {
            int n=0; for(var cert:CertificateFactory.getInstance("X.509").generateCertificates(in)) trust.setCertificateEntry("ca-"+n++,cert);
            if(n==0) throw new IllegalArgumentException("Empty CA bundle.");
        }
        var tmf=TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()); tmf.init(trust);
        return S3Client.builder().endpointOverride(endpoint).region(Region.of(read(base,"region")))
            .forcePathStyle(Boolean.parseBoolean(read(base,"path-style")))
            .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create(read(base,"access-key-id"),read(base,"secret-access-key"))))
            .httpClientBuilder(ApacheHttpClient.builder().tlsTrustManagersProvider(tmf::getTrustManagers).connectionTimeout(Duration.ofSeconds(3)).socketTimeout(Duration.ofSeconds(5)))
            .overrideConfiguration(c->c.apiCallTimeout(Duration.ofSeconds(8)).apiCallAttemptTimeout(Duration.ofSeconds(5))).build();
    }
    @PreDestroy void close() { clients.values().forEach(S3Client::close); }
}
