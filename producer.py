import requests
import psycopg2
import os
import time

#Tämä on toimiva versio

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "weather"),
        user=os.getenv("DB_USER", "rahtitest"),
        password=os.getenv("DB_PASSWORD", "rahtitest")
    )

locations = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]

while True:

    conn = get_connection()
    cur = conn.cursor()

    # päivitä taulu (lisää location!)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id SERIAL PRIMARY KEY,
            location TEXT,
            temp FLOAT,
            wind FLOAT,
            time TEXT
        )
    """)

    # LOOPPI KAIKILLE SIJAINNEILLE
    for location_name, lat, lon in locations:

        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"

        try:
            response = requests.get(url, timeout=5)
            data = response.json()
        except Exception as e:
            print("API error:", e)
            continue

        weather = data.get("current_weather", {})

        entry = (
            location_name,
            weather.get("temperature"),
            weather.get("windspeed"),
            weather.get("time"),
        )

        # tarkista duplikaatti PER LOCATION
        cur.execute("""
            SELECT time FROM weather
            WHERE location = %s
            ORDER BY id DESC LIMIT 1
        """, (location_name,))
        last = cur.fetchone()

        if last and last[0] == entry[3]:
            print(f"{location_name}: Duplicate, skipping")
        else:
            cur.execute(
                "INSERT INTO weather (location, temp, wind, time) VALUES (%s, %s, %s, %s)",
                entry
            )
            conn.commit()
            print("Inserted:", entry)

    cur.close()
    conn.close()

    time.sleep(900)  # 15 min = 900s