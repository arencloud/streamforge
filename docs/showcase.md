# Three-way S3 showcase

Use a dedicated database and bucket/prefixes with synthetic data. The default `all` profile sends the same six-partition `sf.public.orders` topic to independent consumers:

| Implementation | Consumer group | Object prefix | Format/behavior |
| --- | --- | --- | --- |
| Aiven S3 Sink | `connect-aiven-s3` | `aiven/` | Batched JSONL, partition/start-offset file identity |
| Camel Quarkus | `camel-s3` | `camel/` | One JSON envelope per topic/partition/offset |
| Custom Camel Connect | `connect-camel-connect-s3` | `camel-connect/` | Same per-record identity, Connect-managed offsets |

The source task is single-threaded per PostgreSQL replication slot. Two source workers provide failover, not two concurrent source tasks. Each sink can independently replay the topic. Connect sink task count is three; Quarkus has two consumers. Snapshot records have `op=r`; subsequent inserts/updates/deletes have `c/u/d`. Null Kafka tombstones are disabled at the source, but both custom sinks preserve a null value if one is encountered.

1. DBA: provision logical replication and the role, then run `showcase/01-prepare-postgres.sql` using an approved `PGSERVICE`/`.pgpass` configuration outside Git. Pass the role name with `-v cdc_role=streamforge_cdc`. The publication creation is intentionally one-time; inspect an existing publication rather than dropping it to rerun the file.
2. Complete deployment and wait for Kafka, all KafkaConnects, KafkaConnectors and the Camel Deployment to become Ready. Inspect connector **status only**, not resolved REST configurations containing credentials. Verify the initial snapshot completed before generating test events.
3. Run `showcase/02-events.sql`. The fixed test IDs intentionally fail if reused. For another run, use a new dedicated fixture/database or deliberately clean only the synthetic rows after accounting for the resulting delete events. Do not recreate the replication slot to reset a demo.
4. Wait for Connect's flush interval and sink lag to reach zero. Download just the three showcase prefixes through an approved AWS CLI profile. Store downloads outside Git; these are data, not repository fixtures.

```bash
psql service=streamforge-showcase -v cdc_role=streamforge_cdc -f showcase/01-prepare-postgres.sql
# After connectors are Ready and snapshot complete:
psql service=streamforge-showcase -f showcase/02-events.sql
# Set S3_ENDPOINT and S3_BUCKET to non-secret provider settings; use an AWS profile for credentials.
aws --endpoint-url "$S3_ENDPOINT" s3 sync "s3://$S3_BUCKET/aiven/" /tmp/streamforge-results/aiven/
aws --endpoint-url "$S3_ENDPOINT" s3 sync "s3://$S3_BUCKET/camel/" /tmp/streamforge-results/camel/
aws --endpoint-url "$S3_ENDPOINT" s3 sync "s3://$S3_BUCKET/camel-connect/" /tmp/streamforge-results/camel-connect/
python3 showcase/verify.py /tmp/streamforge-results/aiven /tmp/streamforge-results/camel /tmp/streamforge-results/camel-connect
```

The verifier checks the expected synthetic operations and compares normalized CDC envelopes without printing record contents. Use only one directory for a single-sink profile. Aiven can represent the JSON payload as a string inside JSONL; the verifier normalizes that representation. Retried duplicate records are counted and compared as a set, consistent with at-least-once delivery.

Demonstrate an S3 outage in staging by denying access for one dedicated sink credential, write more synthetic events, and observe lag/retry alerts. Restore access and verify the complete event set. Separately restart a worker after a successful PUT but before offset commit, and compare object keys/contents. Do not claim exactly once: S3 versioning may retain multiple versions, Aiven batch boundaries can change after restart, and the source may produce duplicate events at different Kafka offsets.

The Camel variants intentionally favor inspectable correctness over bulk throughput: one PUT per record can be expensive. Aiven batches records and is the baseline for high-throughput object storage. Compare records/sec, API request count, object count/size, delivery latency, CPU, memory, lag and recovery time at the same input rate before choosing a production sink.
