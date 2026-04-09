import requests
import psycopg2
import os
import time

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "weather"),
        user=os.getenv("DB_USER", "rahtitest"),
        password=os.getenv("DB_PASSWORD", "rahtitest")
    )

while True:
    url = "https://api.open-meteo.com/v1/forecast?latitude=65.01&longitude=25.47&current_weather=true"

    try:
        response = requests.get(url, timeout=5)
        data = response.json()
    except Exception as e:
        print("API error:", e)
        time.sleep(5)
        continue

    weather = data.get("current_weather", {})

    entry = (
        weather.get("temperature"),
        weather.get("windspeed"),
        weather.get("time"),
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id SERIAL PRIMARY KEY,
            temp FLOAT,
            wind FLOAT,
            time TEXT
        )
    """)

    # hae viimeisin timestamp
    cur.execute("SELECT time FROM weather ORDER BY id DESC LIMIT 1")
    last = cur.fetchone()

    if last and last[0] == entry[2]:
        print("Duplicate, skipping")
    else:
        cur.execute(
            "INSERT INTO weather (temp, wind, time) VALUES (%s, %s, %s)",
            entry
        )
        conn.commit()
        print("Inserted:", entry)

    cur.close()
    conn.close()

    time.sleep(10)