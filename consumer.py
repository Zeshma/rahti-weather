from kafka import KafkaConsumer
import json
import psycopg2
import os

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

consumer = KafkaConsumer(
    "weather",
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "kafka:9092"),
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

# lue Kafkaa
for msg in consumer:
    data = msg.value

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

        print("Inserted:", data)

    except Exception as e:
        print("DB error:", e)