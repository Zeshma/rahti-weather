from kafka import KafkaConsumer
import json
import psycopg2
import os

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
