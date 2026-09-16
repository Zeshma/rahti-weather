"""Central configuration for the rahti-weather application.

All environment-variable lookups and their defaults live here. The three
entry points (app.py, producer.py, consumer.py) import from this module
instead of reading os.environ directly, so defaults stay in one place.

Database credentials fall back to the POSTGRESQL_* names that the Bitnami
PostgreSQL image sets, matching the original app.py behaviour.
"""

import os


# Map DB_* keys to the POSTGRESQL_* env var names that the Bitnami image sets.
_POSTGRESQL_FALLBACK = {
    "DB_HOST": "POSTGRESQL_HOST",
    "DB_NAME": "POSTGRESQL_DATABASE",
    "DB_USER": "POSTGRESQL_USERNAME",
    "DB_PASSWORD": "POSTGRESQL_PASSWORD",
    "DB_PORT": "POSTGRESQL_PORT",
}


def _db_env(key, default):
    """Read DB_HOST etc., falling back to the POSTGRESQL_* equivalent."""
    return os.environ.get(key, os.environ.get(_POSTGRESQL_FALLBACK.get(key, key), default))


# --- Database ---------------------------------------------------------------
DB_HOST = _db_env("DB_HOST", "postgresql")
DB_NAME = _db_env("DB_NAME", "weatherdb")
DB_USER = _db_env("DB_USER", "weatheruser")
DB_PASSWORD = _db_env("DB_PASSWORD", "weatherpass")
DB_PORT = _db_env("DB_PORT", "5432")

# --- Kafka ------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "weather")
KAFKA_USERNAME = os.getenv("KAFKA_USERNAME", "user1")
KAFKA_PASSWORD = os.getenv("KAFKA_PASSWORD", "")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256")
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
KAFKA_DISABLED = os.getenv("KAFKA_DISABLED", "false").lower() == "true"
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "weather-group")

# --- Application behaviour --------------------------------------------------
COMPONENT = os.getenv("COMPONENT", "web")
STATUS_PAGE_ENABLED = os.getenv("STATUS_PAGE_ENABLED", "true").lower() == "true"

# Locations polled by the producer: (name, latitude, longitude)
LOCATIONS = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]

POLL_INTERVAL_SECONDS = 900  # 15 minutes

# --- Health-check ports -----------------------------------------------------
WEB_PORT = 8080
PRODUCER_HEALTH_PORT = 8081
CONSUMER_HEALTH_PORT = 8082


def db_connection_kwargs():
    """Return kwargs for psycopg2.connect() using the configured values."""
    return {
        "host": DB_HOST,
        "database": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
        "port": DB_PORT,
    }


def kafka_producer_kwargs(value_serializer):
    """Return kwargs for KafkaProducer() using the configured values."""
    return {
        "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
        "value_serializer": value_serializer,
        "security_protocol": KAFKA_SECURITY_PROTOCOL,
        "sasl_mechanism": KAFKA_SASL_MECHANISM,
        "sasl_plain_username": KAFKA_USERNAME,
        "sasl_plain_password": KAFKA_PASSWORD,
    }


def kafka_consumer_kwargs(value_deserializer):
    """Return kwargs for KafkaConsumer() using the configured values.

    The topic is passed positionally by the caller (KafkaConsumer's first
    positional argument), so it is not included here.
    """
    return {
        "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
        "value_deserializer": value_deserializer,
        "auto_offset_reset": "earliest",
        "group_id": KAFKA_GROUP_ID,
        "security_protocol": KAFKA_SECURITY_PROTOCOL,
        "sasl_mechanism": KAFKA_SASL_MECHANISM,
        "sasl_plain_username": KAFKA_USERNAME,
        "sasl_plain_password": KAFKA_PASSWORD,
    }
