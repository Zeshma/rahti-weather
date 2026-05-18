from kafka import KafkaConsumer
import json
import psycopg2
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

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
            # Try to get some metadata from consumer
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
    server = HTTPServer(('0.0.0.0', 8082), HealthRequestHandler)
    server.serve_forever()

def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "<db-host>"),
        database=os.environ.get("DB_NAME", "<db-name>"),
        user=os.environ.get("DB_USER", "<db-user>"),
        password=os.environ.get("DB_PASSWORD", "<db-password>"),
        port=os.environ.get("DB_PORT", "<db-port>")
    )

# Configure Kafka consumer with SASL authentication
consumer = KafkaConsumer(
    os.getenv("KAFKA_TOPIC", "weather"),
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "<kafka-bootstrap-servers>"),
    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    group_id="weather-group-2"
)

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
print(f"Listening to topic: {os.getenv('KAFKA_TOPIC', 'weather')}", flush=True)

# lue Kafkaa
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
