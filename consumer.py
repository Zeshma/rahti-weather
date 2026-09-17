from kafka import KafkaConsumer
import json
import psycopg2
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import config

def check_consumer_health():
    """Check if consumer is healthy"""
    try:
        # Test database connectivity
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        conn.close()

        # Test Kafka connection
        kafka_healthy = True
        try:
            # consumer always exists: if Kafka failed to bootstrap the pod
            # would have exited before the health server started.
            topics = list(consumer.topics())
        except:
            kafka_healthy = False

        if result == (1,) and kafka_healthy:
            return {
                "status": "healthy",
                "database": "connected",
                "kafka": "connected"
            }
        else:
            return {
                "status": "unhealthy",
                "database": "connected" if result == (1,) else "disconnected",
                "kafka": "connected" if kafka_healthy else "disconnected"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

class HealthRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            health_status = check_consumer_health()
            self.send_response(200 if health_status["status"] == "healthy" else 500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_status).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    """Start HTTP server for health checks on port 8082"""
    server = HTTPServer(('0.0.0.0', config.CONSUMER_HEALTH_PORT), HealthRequestHandler)
    server.serve_forever()

def get_connection():
    return psycopg2.connect(**config.db_connection_kwargs())

# Configure Kafka consumer with SASL authentication
try:
    # Retry the bootstrap: Kafka may not be ready yet when the pod starts.
    # Without a retry the consumer falls back to passive mode for the whole
    # lifetime of the pod and never recovers.
    max_attempts = 6
    for attempt in range(1, max_attempts + 1):
        try:
            consumer = KafkaConsumer(
                config.KAFKA_TOPIC,
                **config.kafka_consumer_kwargs(
                    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
                )
            )
            break
        except Exception as e:
            if attempt == max_attempts:
                raise
            print(
                f"Kafka bootstrap attempt {attempt}/{max_attempts} failed: {e}",
                flush=True,
            )
            time.sleep(5)
except Exception as e:
    # Kafka is mandatory: do not fall back to passive mode. Re-raise so the
    # pod exits and restarts, retrying against Kafka.
    print(f"Kafka connection failed, exiting: {e}", flush=True)
    raise

# luo taulu kerran
conn = get_connection()
cur = conn.cursor()

cur.execute("""
    CREATE TABLE IF NOT EXISTS weather (
        id SERIAL PRIMARY KEY,
        location TEXT,
        temp FLOAT,
        wind FLOAT,
        time TEXT
    )
""")
conn.commit()
cur.close()
conn.close()

# Start health check server in background thread
health_thread = threading.Thread(target=start_health_server, daemon=False)
health_thread.start()
print("Started health check server on port 8082", flush=True)

print("Database table created, starting Kafka consumer...", flush=True)
print(f"Listening to topic: {config.KAFKA_TOPIC}", flush=True)

# Kafka is mandatory: the consumer always runs. If Kafka failed to
# bootstrap, the pod exited above before reaching here.
for msg in consumer:
    data = msg.value
    print(f"Received message: {data}", flush=True)

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO weather (location, temp, wind, time)
            VALUES (%s, %s, %s, %s)
        """, (
            data["location"],
            data["temp"],
            data["wind"],
            data["time"]
        ))

        conn.commit()
        cur.close()
        conn.close()

        print("Inserted:", data, flush=True)

    except Exception as e:
        print("DB error:", e, flush=True)

# Passive-mode fallback (DISABLED). Kept commented for reference; to
# re-enable, uncomment and restore the KAFKA_DISABLED guard above.
# else:
#     print("Kafka disabled, consumer running in passive mode", flush=True)
#     # Keep the consumer running indefinitely when Kafka is disabled
#     import time
#     while True:
#         time.sleep(60)
#         print("Consumer in passive mode - Kafka disabled", flush=True)
