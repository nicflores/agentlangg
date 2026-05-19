# syntax=docker/dockerfile:1.7
 
# =============================================================================
# Build arguments — override at build time with `--build-arg`
# =============================================================================
ARG CP_VERSION=7.8.1
ARG JDBC_CONNECTOR_VERSION=10.7.6
ARG PG_DRIVER_VERSION=42.7.4
 
 
# =============================================================================
# Stage 1: builder
# Uses the cp-kafka-connect image purely for its `confluent-hub` CLI and JRE
# (needed to verify connector signatures). Assembles all plugin artifacts
# into a single staging directory that the runtime stage will copy in one shot.
# =============================================================================
FROM confluentinc/cp-kafka-connect:${CP_VERSION} AS builder
 
ARG JDBC_CONNECTOR_VERSION
ARG PG_DRIVER_VERSION
 
# Install the JDBC Sink Connector into an isolated staging tree.
# `--component-dir` keeps everything under /plugins so the COPY into the
# final stage is a single, predictable directory.
RUN confluent-hub install --no-prompt \
      --component-dir /plugins \
      --worker-configs /dev/null \
      confluentinc/kafka-connect-jdbc:${JDBC_CONNECTOR_VERSION}
 
# Drop the Postgres JDBC driver into the connector's lib/ directory.
# Placing it inside the connector folder (rather than /usr/share/java) keeps
# the driver scoped to this plugin and avoids classloader conflicts with
# other connectors that might be added later.
RUN curl -fsSL --retry 3 --retry-delay 2 \
      "https://jdbc.postgresql.org/download/postgresql-${PG_DRIVER_VERSION}.jar" \
      -o /plugins/confluentinc-kafka-connect-jdbc/lib/postgresql-${PG_DRIVER_VERSION}.jar \
 && test -s /plugins/confluentinc-kafka-connect-jdbc/lib/postgresql-${PG_DRIVER_VERSION}.jar
 
 
# =============================================================================
# Stage 2: runtime
# Final image. No curl, no confluent-hub CLI, no build leftovers — just the
# Connect worker + the JDBC sink plugin + the Postgres driver.
# =============================================================================
FROM confluentinc/cp-kafka-connect:${CP_VERSION}
 
ARG CP_VERSION
ARG JDBC_CONNECTOR_VERSION
ARG PG_DRIVER_VERSION
 
LABEL org.opencontainers.image.title="kafka-connect-postgres-sink" \
      org.opencontainers.image.description="Kafka Connect worker with Confluent JDBC Sink Connector and PostgreSQL driver" \
      cp.version="${CP_VERSION}" \
      jdbc.connector.version="${JDBC_CONNECTOR_VERSION}" \
      postgres.driver.version="${PG_DRIVER_VERSION}"
 
# Copy the assembled plugin tree from the builder stage.
COPY --from=builder /plugins /usr/share/confluent-hub-components
 
# ---------------------------------------------------------------------------
# Kafka Connect configuration via environment variables.
#
# The Confluent entrypoint translates CONNECT_<UPPER_SNAKE_CASE> environment
# variables into the corresponding `connect-distributed.properties` keys
# (lowercased, underscores replaced with dots). Every value below can be
# overridden at deploy time (e.g. in Azure Container Apps env settings or
# via a Key Vault secret reference).
# ---------------------------------------------------------------------------
 
# --- Required: Kafka broker connectivity (set at deploy time) ----------------
ENV CONNECT_BOOTSTRAP_SERVERS=""
 
# --- Worker identity --------------------------------------------------------
# group.id must be unique across Connect clusters sharing the same Kafka.
ENV CONNECT_GROUP_ID="kafka-connect-postgres-sink"
 
# --- Internal Kafka topics for Connect state --------------------------------
# These topics must exist (or be auto-creatable) before the worker starts.
# Use compacted topics in production.
ENV CONNECT_CONFIG_STORAGE_TOPIC="_connect-configs" \
    CONNECT_OFFSET_STORAGE_TOPIC="_connect-offsets" \
    CONNECT_STATUS_STORAGE_TOPIC="_connect-status" \
    CONNECT_CONFIG_STORAGE_REPLICATION_FACTOR="3" \
    CONNECT_OFFSET_STORAGE_REPLICATION_FACTOR="3" \
    CONNECT_STATUS_STORAGE_REPLICATION_FACTOR="3" \
    CONNECT_OFFSET_STORAGE_PARTITIONS="25" \
    CONNECT_STATUS_STORAGE_PARTITIONS="5"
 
# --- Message converters (schemaless JSON by default) ------------------------
# Override these if you use Schema Registry with Avro/Protobuf/JSON Schema.
ENV CONNECT_KEY_CONVERTER="org.apache.kafka.connect.json.JsonConverter" \
    CONNECT_KEY_CONVERTER_SCHEMAS_ENABLE="false" \
    CONNECT_VALUE_CONVERTER="org.apache.kafka.connect.json.JsonConverter" \
    CONNECT_VALUE_CONVERTER_SCHEMAS_ENABLE="false" \
    CONNECT_INTERNAL_KEY_CONVERTER="org.apache.kafka.connect.json.JsonConverter" \
    CONNECT_INTERNAL_VALUE_CONVERTER="org.apache.kafka.connect.json.JsonConverter"
 
# --- Plugin discovery -------------------------------------------------------
ENV CONNECT_PLUGIN_PATH="/usr/share/java,/usr/share/confluent-hub-components"
 
# --- REST API ---------------------------------------------------------------
# Port 8083 is used for connector registration and health checks.
# CONNECT_REST_ADVERTISED_HOST_NAME must be set at deploy time to a value
# other replicas can resolve (the ACA replica's internal hostname/FQDN).
ENV CONNECT_REST_PORT="8083" \
    CONNECT_LISTENERS="http://0.0.0.0:8083" \
    CONNECT_REST_ADVERTISED_HOST_NAME=""
 
# --- Logging ----------------------------------------------------------------
ENV CONNECT_LOG4J_ROOT_LOGLEVEL="INFO" \
    CONNECT_LOG4J_LOGGERS="org.apache.kafka.connect.runtime.rest=WARN,org.reflections=ERROR"
 
# --- Error handling defaults (override per-connector as needed) -------------
ENV CONNECT_ERRORS_TOLERANCE="none" \
    CONNECT_ERRORS_LOG_ENABLE="true" \
    CONNECT_ERRORS_LOG_INCLUDE_MESSAGES="false"
 
# ---------------------------------------------------------------------------
# Optional configuration — uncomment or override at deploy time
# ---------------------------------------------------------------------------
 
# --- Schema Registry (Avro / JSON Schema / Protobuf) ------------------------
# ENV CONNECT_KEY_CONVERTER="io.confluent.connect.avro.AvroConverter"
# ENV CONNECT_KEY_CONVERTER_SCHEMA_REGISTRY_URL=""
# ENV CONNECT_VALUE_CONVERTER="io.confluent.connect.avro.AvroConverter"
# ENV CONNECT_VALUE_CONVERTER_SCHEMA_REGISTRY_URL=""
 
# --- SASL / SSL (e.g. Confluent Cloud, Azure Event Hubs for Kafka, MSK) -----
# ENV CONNECT_SECURITY_PROTOCOL="SASL_SSL"
# ENV CONNECT_SASL_MECHANISM="PLAIN"
# ENV CONNECT_SASL_JAAS_CONFIG=""
# ENV CONNECT_PRODUCER_SECURITY_PROTOCOL="SASL_SSL"
# ENV CONNECT_PRODUCER_SASL_MECHANISM="PLAIN"
# ENV CONNECT_PRODUCER_SASL_JAAS_CONFIG=""
# ENV CONNECT_CONSUMER_SECURITY_PROTOCOL="SASL_SSL"
# ENV CONNECT_CONSUMER_SASL_MECHANISM="PLAIN"
# ENV CONNECT_CONSUMER_SASL_JAAS_CONFIG=""
 
# --- Dead-letter queue (highly recommended for sink connectors) -------------
# Set these per-connector in the connector config rather than globally:
#   "errors.deadletterqueue.topic.name": "dlq-postgres-sink"
#   "errors.deadletterqueue.topic.replication.factor": "3"
#   "errors.tolerance": "all"
 
# --- JVM tuning -------------------------------------------------------------
# ENV KAFKA_HEAP_OPTS="-Xms1G -Xmx2G"
# ENV KAFKA_JVM_PERFORMANCE_OPTS="-XX:+UseG1GC -XX:MaxGCPauseMillis=20"
 
# ---------------------------------------------------------------------------
# Healthcheck — Kafka Connect's REST API root endpoint returns version info
# once the worker has started. ACA uses HTTP probes defined in the Container
# App spec, but this HEALTHCHECK helps local `docker run` and any platform
# that reads OCI healthcheck metadata.
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl -fsS http://localhost:8083/ || exit 1
 
EXPOSE 8083
 
# The base image's entrypoint runs connect-distributed with the env-derived
# config; no CMD or ENTRYPOINT override is needed.