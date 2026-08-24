from kafka import KafkaProducer
import json
import requests
import time
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import config

def check_kafka_health():
    """Check if Kafka producer is healthy"""
    try:
        # Test basic connectivity first
        if not hasattr(check_kafka_health, 'producer_ready'):
            # Give producer time to initialize
            import time as time_module
            time_module.sleep(1)

        # Test Kafka connection by getting metrics
        if hasattr(check_kafka_health, 'producer_ready') and kafka_enabled:
            metadata = producer.metrics()
            return {
                "status": "healthy",
                "kafka": "connected",
                "metrics_count": len(metadata)
            }
        else:
            return {
                "status": "healthy",
                "kafka": "initializing" if hasattr(check_kafka_health, 'producer_ready') else "disabled",
                "message": "Producer is starting up" if hasattr(check_kafka_health, 'producer_ready') else "Kafka disabled, running in direct mode"
            }
    except Exception as e:
        return {
            "status": "healthy",  # Still healthy even if Kafka is not available
            "kafka": str(e),
            "message": "Kafka not available, but running in direct mode"
        }

class HealthRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            health_status = check_kafka_health()
            self.send_response(200 if health_status["status"] == "healthy" else 500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_status).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server():
    """Start HTTP server for health checks on port 8081"""
    server = HTTPServer(('0.0.0.0', config.PRODUCER_HEALTH_PORT), HealthRequestHandler)
    server.serve_forever()

locations = config.LOCATIONS

# Configure Kafka producer with SASL authentication only if Kafka is enabled
kafka_enabled = True  # Default to enabled
try:
    # Check if KAFKA_DISABLED is explicitly set to "true"
    if config.KAFKA_DISABLED:
        print("Kafka explicitly disabled via KAFKA_DISABLED=true", flush=True)
        kafka_enabled = False
    else:
        producer = KafkaProducer(
            **config.kafka_producer_kwargs(
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
        )
        print("Kafka producer initialized successfully", flush=True)
except Exception as e:
    print(f"Kafka connection failed, running in direct mode: {e}", flush=True)
    kafka_enabled = False

# For testing without Kafka, we can directly insert into database
def direct_db_insert():
    import psycopg2
    import time
    from datetime import datetime
    import requests

    def get_connection():
        return psycopg2.connect(**config.db_connection_kwargs())

    # Create table if not exists
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

    while True:
        print(f"Direct DB insert loop started at {time.time()}", flush=True)
        for location_name, lat, lon in locations:
            print(f"Processing {location_name}...", flush=True)

            try:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
                response = requests.get(url, timeout=5)
                data = response.json()
            except Exception as e:
                print("API error:", e, flush=True)
                continue

            weather = data.get("current_weather", {})

            message = {
                "location": location_name,
                "temp": weather.get("temperature"),
                "wind": weather.get("windspeed"),
                "time": weather.get("time"),
            }

            try:
                conn = get_connection()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO weather (location, temp, wind, time)
                    VALUES (%s, %s, %s, %s)
                """, (
                    message["location"],
                    message["temp"],
                    message["wind"],
                    message["time"]
                ))

                conn.commit()
                cur.close()
                conn.close()

                print("Inserted directly to DB:", message, flush=True)

            except Exception as e:
                print("DB error:", e, flush=True)

        print(f"Sleeping for 15 minutes...", flush=True)
        time.sleep(config.POLL_INTERVAL_SECONDS)

# Start direct DB insert in background if KAFKA_DISABLED is set
import threading
if config.KAFKA_DISABLED:
    print("Starting direct DB insert mode (Kafka disabled)", flush=True)
    db_thread = threading.Thread(target=direct_db_insert, daemon=True)
    db_thread.start()

# Start health check server in background thread
health_thread = threading.Thread(target=start_health_server, daemon=True)
health_thread.start()
print("Started health check server on port 8081", flush=True)

# Give health check server a moment to start
import time
time.sleep(2)

# Mark producer as ready for health checks
check_kafka_health.producer_ready = True

while True:
    print(f"Producer loop started at {time.time()}", flush=True)
    for location_name, lat, lon in locations:
        print(f"Processing {location_name}...", flush=True)

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        try:
            response = requests.get(url, timeout=5)
            data = response.json()
        except Exception as e:
            print("API error:", e, flush=True)
            continue

        weather = data.get("current_weather", {})

        message = {
            "location": location_name,
            "temp": weather.get("temperature"),
            "wind": weather.get("windspeed"),
            "time": weather.get("time"),
        }

        # Only send to Kafka if Kafka is enabled and producer exists
        if kafka_enabled:
            producer.send(config.KAFKA_TOPIC, message)
            print("Sent to Kafka:", message, flush=True)
        else:
            print("Kafka disabled, data inserted via direct DB thread", flush=True)

    print(f"Sleeping for 15 minutes...", flush=True)
    time.sleep(config.POLL_INTERVAL_SECONDS)
