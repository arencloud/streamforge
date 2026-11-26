package com.streamforge.s3;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import jakarta.enterprise.inject.Disposes;
import jakarta.inject.Named;
import org.apache.camel.component.kafka.KafkaComponent;
import org.apache.camel.component.kafka.consumer.DefaultKafkaManualCommitFactory;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import software.amazon.awssdk.auth.credentials.EnvironmentVariableCredentialsProvider;
import software.amazon.awssdk.http.apache.ApacheHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;

import javax.net.ssl.TrustManagerFactory;
import java.io.InputStream;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.security.cert.CertificateFactory;
import java.time.Duration;

@ApplicationScoped
public class Clients {
    @ConfigProperty(name = "streamforge.kafka.bootstrap") String bootstrap;
    @ConfigProperty(name = "streamforge.kafka.username") String username;
    @ConfigProperty(name = "streamforge.kafka.password") String password;
    @ConfigProperty(name = "streamforge.kafka.ca") String kafkaCa;
    @ConfigProperty(name = "streamforge.s3.endpoint") String endpoint;
    @ConfigProperty(name = "streamforge.s3.region") String region;
    @ConfigProperty(name = "streamforge.s3.path-style") boolean pathStyle;
    @ConfigProperty(name = "streamforge.s3.ca") String s3Ca;

    @Produces @Named("kafka") @ApplicationScoped
    public KafkaComponent kafka() throws Exception {
        KafkaComponent component = new KafkaComponent();
        var c = component.getConfiguration();
        c.setBrokers(bootstrap);
        c.setSecurityProtocol("SASL_SSL");
        c.setSaslMechanism("SCRAM-SHA-512");
        c.setSaslJaasConfig("org.apache.kafka.common.security.scram.ScramLoginModule required username="
                + jaasQuote(username) + " password=" + jaasQuote(password) + ";");
        c.setSslTruststoreType("PEM");
        c.setSslTruststoreLocation(kafkaCa);
        c.setSslEndpointAlgorithm("https");
        c.setAutoCommitEnable(false);
        c.setAllowManualCommit(true);
        c.setBreakOnFirstError(true);
        c.setMaxPollRecords(1);
        c.setMaxPollIntervalMs(300000);
        c.setAutoOffsetReset("earliest");
        // Select SyncCommitManager: failures seek back to the failed offset.
        component.setKafkaManualCommitFactory(new DefaultKafkaManualCommitFactory());
        return component;
    }

    static String jaasQuote(String value) {
        if (value.indexOf('\n') >= 0 || value.indexOf('\r') >= 0) {
            throw new IllegalArgumentException("Kafka credentials must not contain newlines");
        }
        return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    @Produces @Named("s3Client") @ApplicationScoped
    public S3Client s3() throws Exception {
        URI uri = URI.create(endpoint);
        if (!"https".equals(uri.getScheme()) || uri.getUserInfo() != null) {
            throw new IllegalArgumentException("S3 endpoint must use HTTPS without embedded credentials");
        }
        KeyStore trust = KeyStore.getInstance(KeyStore.getDefaultType());
        trust.load(null, null);
        try (InputStream input = Files.newInputStream(Path.of(s3Ca))) {
            int n = 0;
            for (var cert : CertificateFactory.getInstance("X.509").generateCertificates(input)) {
                trust.setCertificateEntry("ca-" + n++, cert);
            }
            if (n == 0) throw new IllegalArgumentException("Empty S3 CA bundle");
        }
        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        tmf.init(trust);
        return S3Client.builder()
                .region(Region.of(region))
                .endpointOverride(uri)
                .forcePathStyle(pathStyle)
                .credentialsProvider(EnvironmentVariableCredentialsProvider.create())
                .httpClientBuilder(ApacheHttpClient.builder()
                        .connectionTimeout(Duration.ofSeconds(5))
                        .socketTimeout(Duration.ofSeconds(20))
                        .tlsTrustManagersProvider(tmf::getTrustManagers))
                .overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(45))
                        .apiCallAttemptTimeout(Duration.ofSeconds(20)))
                .build();
    }

    void closeS3(@Disposes @Named("s3Client") S3Client client) {
        client.close();
    }
}
