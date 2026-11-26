package com.streamforge.connect;

import org.apache.kafka.common.config.ConfigDef;
import org.apache.kafka.connect.connector.Task;
import org.apache.kafka.connect.sink.SinkConnector;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class CamelS3SinkConnector extends SinkConnector {
    private Map<String, String> properties;
    public static final ConfigDef CONFIG = new ConfigDef()
            .define("s3.endpoint", ConfigDef.Type.STRING, ConfigDef.NO_DEFAULT_VALUE, ConfigDef.Importance.HIGH, "HTTPS S3 endpoint")
            .define("s3.region", ConfigDef.Type.STRING, ConfigDef.NO_DEFAULT_VALUE, ConfigDef.Importance.HIGH, "S3 signing region")
            .define("s3.bucket", ConfigDef.Type.STRING, ConfigDef.NO_DEFAULT_VALUE, ConfigDef.Importance.HIGH, "Pre-created bucket")
            .define("s3.prefix", ConfigDef.Type.STRING, "camel-connect/", ConfigDef.Importance.MEDIUM, "Object prefix")
            .define("s3.path.style", ConfigDef.Type.BOOLEAN, true, ConfigDef.Importance.MEDIUM, "Path-style requests")
            .define("s3.ca.path", ConfigDef.Type.STRING, "/mnt/s3-ca/ca.crt", ConfigDef.Importance.HIGH, "PEM CA bundle path");
    @Override public String version() { return "0.1.0"; }
    @Override public void start(Map<String, String> props) {
        new org.apache.kafka.common.config.AbstractConfig(CONFIG, props, false);
        properties = new HashMap<>(props);
    }
    @Override public Class<? extends Task> taskClass() { return CamelS3SinkTask.class; }
    @Override public List<Map<String, String>> taskConfigs(int maxTasks) {
        var result = new ArrayList<Map<String, String>>();
        for (int i = 0; i < maxTasks; i++) result.add(new HashMap<>(properties));
        return result;
    }
    @Override public void stop() { }
    @Override public ConfigDef config() { return CONFIG; }
}
