from kafka import KafkaProducer
import json
import requests
import time
import os
import sys
import datetime
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
                "kafka": "initializing",
                "message": "Producer is starting up"
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "kafka": str(e),
            "message": "Kafka not available"
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

# Configure Kafka producer. Kafka is mandatory: if bootstrap fails after
# retries, re-raise so the pod crashes and restarts (visible failure) rather
# than silently degrading.
kafka_enabled = True  # Default to enabled
try:
    # Direct-DB fallback (KAFKA_DISABLED) is disabled in this deployment.
    # To re-enable for local testing, uncomment the block below:
    #   # Check if KAFKA_DISABLED is explicitly set to "true"
    #   if config.KAFKA_DISABLED:
    #       print("Kafka explicitly disabled via KAFKA_DISABLED=true", flush=True)
    #       kafka_enabled = False
    #   else:
    #       ...retry loop...
    # For the Kafka-mandatory path we always run the retry loop:
    # Retry the bootstrap: Kafka may not be ready yet when the pod starts,
    # and the default KafkaProducer timeout is short. Without a retry the
    # producer fails before Kafka is up.
    max_attempts = 6
    for attempt in range(1, max_attempts + 1):
        try:
            producer = KafkaProducer(
                **config.kafka_producer_kwargs(
                    value_serializer=lambda v: json.dumps(v).encode("utf-8")
                )
            )
            print("Kafka producer initialized successfully", flush=True)
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
    # Kafka is mandatory: do not fall back to direct mode. Re-raise so the
    # pod exits and restarts, retrying against Kafka.
    print(f"Kafka connection failed, exiting: {e}", flush=True)
    raise

# --- Direct-DB fallback (DISABLED) -------------------------------------------
# This path bypasses Kafka and writes weather data straight to PostgreSQL.
# It is disabled in this Kafka-mandatory deployment. To re-enable for local
# testing without Kafka, uncomment this function and the thread-start block
# below, and set KAFKA_DISABLED=true (also uncomment the KAFKA_DISABLED
# branch in the bootstrap block above and in config.py).
#
# # For testing without Kafka, we can directly insert into database
# def direct_db_insert():
#     import psycopg2
#     import time
#     from datetime import datetime
#     import requests
#
#     def get_connection():
#         return psycopg2.connect(**config.db_connection_kwargs())
#
#     # Create table if not exists
#     conn = get_connection()
#     cur = conn.cursor()
#     cur.execute("""
#         CREATE TABLE IF NOT EXISTS weather (
#             id SERIAL PRIMARY KEY,
#             location TEXT,
#             temp FLOAT,
#             wind FLOAT,
#             time TEXT
#         )
#     """)
#     conn.commit()
#     cur.close()
#     conn.close()
#
#     while True:
#         print(f"Direct DB insert loop started at {time.time()}", flush=True)
#         for location_name, lat, lon in locations:
#             print(f"Processing {location_name}...", flush=True)
#
#             try:
#                 url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
#                 response = requests.get(url, timeout=5)
#                 data = response.json()
#             except Exception as e:
#                 print("API error:", e, flush=True)
#                 continue
#
#             weather = data.get("current_weather", {})
#
#             message = {
#                 "location": location_name,
#                 "temp": weather.get("temperature"),
#                 "wind": weather.get("windspeed"),
#                 "time": weather.get("time"),
#             }
#
#             try:
#                 conn = get_connection()
#                 cur = conn.cursor()
#
#                 cur.execute("""
#                     INSERT INTO weather (location, temp, wind, time)
#                     VALUES (%s, %s, %s, %s)
#                 """, (
#                     message["location"],
#                     message["temp"],
#                     message["wind"],
#                     message["time"]
#                 ))
#
#                 conn.commit()
#                 cur.close()
#                 conn.close()
#
#                 print("Inserted directly to DB:", message, flush=True)
#
#             except Exception as e:
#                 print("DB error:", e, flush=True)
#
#         print(f"Sleeping for 15 minutes...", flush=True)
#         time.sleep(config.POLL_INTERVAL_SECONDS)
#
# # Start direct DB insert in background if KAFKA_DISABLED is set
# import threading
# if config.KAFKA_DISABLED:
#     print("Starting direct DB insert mode (Kafka disabled)", flush=True)
#     db_thread = threading.Thread(target=direct_db_insert, daemon=True)
#     db_thread.start()
# --- End direct-DB fallback (DISABLED) ----------------------------------------

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

        # Send to Kafka. Kafka is mandatory; if it were disabled the pod
        # would have exited during bootstrap above.
        producer.send(config.KAFKA_TOPIC, message)
        print("Sent to Kafka:", message, flush=True)
        # Direct-DB fallback (DISABLED). The else branch below was misleading:
        # it logged "data inserted via direct DB thread" without inserting
        # anything, causing silent data loss. Kept commented for reference.
        # else:
        #     print("Kafka disabled, data inserted via direct DB thread", flush=True)

    # Fixed-schedule sleep: poll at minutes 1, 16, 31, 46 past the hour
    # (UTC, matching the pod clock). This keeps polls aligned to the clock
    # instead of drifting from pod start time.
    POLL_MINUTES = config.POLL_MINUTES_UTC
    now = datetime.datetime.utcnow()
    upcoming = [m for m in POLL_MINUTES if m > now.minute]
    if upcoming:
        next_min = upcoming[0]
        next_time = now.replace(minute=next_min, second=0, microsecond=0)
    else:
        # Next poll is in the following hour
        next_min = POLL_MINUTES[0]
        next_time = (now.replace(minute=0, second=0, microsecond=0)
                     + datetime.timedelta(hours=1, minutes=next_min))
    sleep_seconds = (next_time - now).total_seconds()
    print(f"Sleeping {sleep_seconds:.0f}s until {next_time:%H:%M} UTC...", flush=True)
    time.sleep(sleep_seconds)
