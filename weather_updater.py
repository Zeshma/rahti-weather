#!/usr/bin/env python3
import requests
import psycopg2
import os
import datetime
import json

def get_connection():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "<db-host>"),
        database=os.environ.get("DB_NAME", "<db-name>"),
        user=os.environ.get("DB_USER", "<db-user>"),
        password=os.environ.get("DB_PASSWORD", "<db-password>"),
        port=os.environ.get("DB_PORT", "<db-port>")
    )

def fetch_weather_data():
    locations = [
        ("Oulu", 65.01, 25.47),
        ("Lapinaho", 65.89532, 28.30994),
    ]

    weather_data = []

    for location_name, lat, lon in locations:
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(url, timeout=10)
            data = response.json()

            weather = data.get("current_weather", {})
            weather_data.append({
                "location": location_name,
                "temp": weather.get("temperature"),
                "wind": weather.get("windspeed"),
                "time": datetime.datetime.now().isoformat()
            })
        except Exception as e:
            print(f"Error fetching weather for {location_name}: {e}")
            continue

    return weather_data

def update_database(weather_data):
    conn = get_connection()
    cur = conn.cursor()

    for data in weather_data:
        try:
            cur.execute("""
                INSERT INTO weather (location, temp, wind, time)
                VALUES (%s, %s, %s, %s)
            """, (data["location"], data["temp"], data["wind"], data["time"]))
            print(f"Updated {data['location']}: Temp {data['temp']}°C, Wind {data['wind']} m/s")
        except Exception as e:
            print(f"Error updating database for {data['location']}: {e}")

    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("Fetching weather data...")
    weather_data = fetch_weather_data()
    if weather_data:
        print(f"Fetched data for {len(weather_data)} locations")
        update_database(weather_data)
        print("Weather data updated successfully!")
    else:
        print("No weather data fetched")