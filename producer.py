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


# init DB (tehdään vain kerran)
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


locations = [
    ("Oulu", 65.01, 25.47),
    ("Lapinaho", 65.89532, 28.30994),
]


while True:

    conn = get_connection()
    cur = conn.cursor()

    for location_name, lat, lon in locations:

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=temperature_2m,windspeed_10m"
            f"&timezone=auto"
        )

        try:
            response = requests.get(url, timeout=5)

            if response.status_code != 200:
                print("HTTP ERROR:", response.status_code)
                continue

            data = response.json()

            # ota viimeisin datapiste
            weather = {
                "temperature": data["hourly"]["temperature_2m"][-1],
                "windspeed": data["hourly"]["windspeed_10m"][-1],
                "time": data["hourly"]["time"][-1],
            }

        except Exception as e:
            print("API/PARSE ERROR:", e)
            continue

        entry = (
            location_name,
            weather["temperature"],
            weather["windspeed"],
            weather["time"],
        )

        # tarkista duplikaatti
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

    time.sleep(300)