package com.streamforge.connect;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.camel.CamelContext;
import org.apache.camel.ProducerTemplate;
import org.apache.camel.component.aws2.s3.AWS2S3Constants;
import org.apache.camel.impl.DefaultCamelContext;
import org.apache.kafka.common.config.AbstractConfig;
import org.apache.kafka.connect.errors.ConnectException;
import org.apache.kafka.connect.errors.DataException;
import org.apache.kafka.connect.errors.RetriableException;
import org.apache.kafka.connect.sink.SinkRecord;
import org.apache.kafka.connect.sink.SinkTask;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.http.apache.ApacheHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;

import javax.net.ssl.TrustManagerFactory;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.time.Duration;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ThreadLocalRandom;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class CamelS3SinkTask extends SinkTask {
    private static final ObjectMapper JSON = new ObjectMapper();
    private static final Logger LOG = LoggerFactory.getLogger(CamelS3SinkTask.class);
    private CamelContext camel;
    private ProducerTemplate producer;
    private S3Client s3;
    private String endpoint;
    private String prefix = "camel-connect/";
    private int consecutiveFailures;

    @Override public String version() { return "0.1.0"; }

    @Override public void start(Map<String, String> props) {
        var config = new AbstractConfig(CamelS3SinkConnector.CONFIG, props, false);
        try {
            URI uri = URI.create(config.getString("s3.endpoint"));
            if (!"https".equals(uri.getScheme()) || uri.getUserInfo() != null) {
                throw new IllegalArgumentException("HTTPS endpoint without embedded credentials is required");
            }
            prefix = config.getString("s3.prefix");
            if (!prefix.matches("[A-Za-z0-9/_-]+/")) throw new IllegalArgumentException("Invalid prefix");
            String bucket = config.getString("s3.bucket");
            if (!bucket.matches("[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")) throw new IllegalArgumentException("Invalid bucket");
            s3 = createClient(config);
            camel = new DefaultCamelContext();
            camel.getRegistry().bind("s3Client", s3);
            camel.start();
            producer = camel.createProducerTemplate();
            endpoint = "aws2-s3:" + bucket + "?amazonS3Client=#s3Client&autoCreateBucket=false";
        } catch (Exception error) {
            stop();
            // Avoid embedding credentials or data in exception messages.
            throw new ConnectException("Camel S3 task initialization failed; verify endpoint, trust and credentials");
        }
    }

    protected S3Client createClient(AbstractConfig config) throws Exception {
        KeyStore trust = KeyStore.getInstance(KeyStore.getDefaultType());
        trust.load(null, null);
        try (var input = Files.newInputStream(Path.of(config.getString("s3.ca.path")))) {
            int n = 0;
            for (var cert : CertificateFactory.getInstance("X.509").generateCertificates(input)) {
                trust.setCertificateEntry("ca-" + n++, cert);
            }
            if (n == 0) throw new IllegalArgumentException("Empty S3 CA bundle");
        }
        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        tmf.init(trust);
        return S3Client.builder().endpointOverride(URI.create(config.getString("s3.endpoint")))
                .region(Region.of(config.getString("s3.region")))
                .forcePathStyle(config.getBoolean("s3.path.style"))
                .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
                .httpClientBuilder(ApacheHttpClient.builder().connectionTimeout(Duration.ofSeconds(5))
                        .socketTimeout(Duration.ofSeconds(20)).tlsTrustManagersProvider(tmf::getTrustManagers))
                .overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(45))
                        .apiCallAttemptTimeout(Duration.ofSeconds(20))).build();
    }

    @Override public void put(Collection<SinkRecord> records) {
        for (SinkRecord record : records) {
            byte[] payload = encode(record);
            String key = objectKey(prefix, record);
            try {
                write(key, payload);
            } catch (Exception error) {
                // Connect retries the batch. Already-written objects get the same keys on replay.
                long delay = retryDelay(++consecutiveFailures);
                if (context != null) context.timeout(delay);
                LOG.warn("S3 delivery failed; retrying uncommitted records after {} ms", delay);
                throw new RetriableException("S3 write failed; offsets must not advance");
            }
        }
        // All writes are synchronous. Connect may now flush/commit its consumed offsets.
        consecutiveFailures = 0;
    }

    static long retryDelay(int failures) {
        long ceiling = Math.min(30000L, 1000L << Math.min(Math.max(failures - 1, 0), 5));
        return ThreadLocalRandom.current().nextLong(ceiling / 2, ceiling + 1);
    }

    protected void write(String key, byte[] payload) {
        producer.sendBodyAndHeaders(endpoint, payload, Map.of(
                AWS2S3Constants.KEY, key, AWS2S3Constants.CONTENT_TYPE, "application/json"));
    }

    static String objectKey(String prefix, SinkRecord record) {
        return prefix + record.topic() + "/" + record.kafkaPartition() + "/" + record.kafkaOffset() + ".json";
    }

    static byte[] encode(SinkRecord record) {
        try {
            var data = new LinkedHashMap<String, Object>();
            data.put("topic", record.topic());
            data.put("partition", record.kafkaPartition());
            data.put("offset", record.kafkaOffset());
            data.put("timestamp", record.timestamp());
            // StringConverter is required; JSON objects remain structured in S3.
            data.put("key", record.key() == null ? null : JSON.readTree((String) record.key()));
            data.put("value", record.value() == null ? null : JSON.readTree((String) record.value()));
            return JSON.writeValueAsBytes(data);
        } catch (Exception error) {
            throw new DataException("Expected JSON strings or null; record rejected without committing offsets");
        }
    }

    @Override public void stop() {
        try { if (producer != null) producer.stop(); } catch (Exception ignored) { }
        try { if (camel != null) camel.stop(); } catch (Exception ignored) { }
        if (s3 != null) s3.close();
    }
}
