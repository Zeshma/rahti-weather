from kafka import KafkaProducer
import json
import requests
import time
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

def check_kafka_health():
    """Check if Kafka producer is healthy"""
    try:
        # Test basic connectivity first
        if not hasattr(check_kafka_health, 'producer_ready'):
            # Give producer time to initialize
            import time as time_module
            time_module.sleep(1)

        # Test Kafka connection by getting metrics
        if hasattr(check_kafka_health, 'producer_ready'):
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
            "kafka": str(e)
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
    server = HTTPServer(('0.0.0.0', 8081), HealthRequestHandler)
    server.serve_forever()

# Configure Kafka producer with SASL authentication
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "<kafka-bootstrap-servers>"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    security_protocol="SASL_PLAINTEXT",
    sasl_mechanism="SCRAM-SHA-256",
    sasl_plain_username="user1",
    sasl_plain_password=os.getenv("KAFKA_PASSWORD", "<kafka-password>")
)

locations = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]

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

        producer.send(os.getenv("KAFKA_TOPIC", "weather"), message)
        print("Sent:", message, flush=True)

    print(f"Sleeping for 15 minutes...", flush=True)
    time.sleep(900)
