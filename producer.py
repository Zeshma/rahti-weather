from kafka import KafkaProducer
import json
import requests
import time
import os

# Configure Kafka producer with SASL authentication
producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "<kafka-bootstrap-servers>"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    security_protocol="SASL_PLAINTEXT",
    sasl_mechanism="SCRAM-SHA-256",
    sasl_plain_username=os.getenv("KAFKA_USERNAME", "<kafka-username>"),
    sasl_plain_password=os.getenv("KAFKA_PASSWORD", "<kafka-password>")
)

locations = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]

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
