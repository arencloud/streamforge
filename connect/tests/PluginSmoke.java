import java.util.Map;

/** Exercises the actual Kafka Connect plugin classloader without contacting Kafka or S3. */
public final class PluginSmoke {
    public static void main(String[] args) throws Exception {
        Class<?> pluginsType = Class.forName("org.apache.kafka.connect.runtime.isolation.Plugins");
        Object plugins = pluginsType.getConstructor(Map.class).newInstance(Map.of(
                "plugin.path", "/opt/kafka/plugins",
                "plugin.discovery", "hybrid_warn"));
        ClassLoader previousLoader = Thread.currentThread().getContextClassLoader();
        try {
            Object connector = pluginsType.getMethod("newConnector", String.class).invoke(plugins, args[0]);
            Class<?> type = connector.getClass();
            // The worker invokes plugin callbacks with the plugin context classloader.
            Thread.currentThread().setContextClassLoader(type.getClassLoader());
            Object config = type.getMethod("config").invoke(connector);
            if (config == null) throw new IllegalStateException("Connector config is missing");
            Class<?> taskType = (Class<?>) type.getMethod("taskClass").invoke(connector);
            taskType.getConstructor().newInstance();
            System.out.println("PLUGIN_SMOKE_PASS " + type.getName() + " version="
                    + type.getMethod("version").invoke(connector));
        } finally {
            Thread.currentThread().setContextClassLoader(previousLoader);
            if (plugins instanceof AutoCloseable) ((AutoCloseable) plugins).close();
        }
    }
}
