from kafka import KafkaProducer
import json
import requests
import time

producer = KafkaProducer(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "my-cluster-kafka-bootstrap:9092"),
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

locations = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]

while True:
    for location_name, lat, lon in locations:

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        try:
            response = requests.get(url, timeout=5)
            data = response.json()
        except Exception as e:
            print("API error:", e)
            continue

        weather = data.get("current_weather", {})

        message = {
            "location": location_name,
            "temp": weather.get("temperature"),
            "wind": weather.get("windspeed"),
            "time": weather.get("time"),
        }

        producer.send("weather", message)
        print("Sent:", message)

    time.sleep(900)