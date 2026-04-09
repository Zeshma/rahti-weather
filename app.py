from flask import Flask, render_template_string
import psycopg2
import os
from datetime import datetime, timedelta

app = Flask(__name__)

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "weather"),
        user=os.getenv("DB_USER", "rahtitest"),
        password=os.getenv("DB_PASSWORD", "rahtitest")
    )

@app.route("/")
def home():
    conn = get_connection()
    cur = conn.cursor()

    # varmista että taulu on olemassa (uusi rakenne)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id SERIAL PRIMARY KEY,
            location TEXT,
            temp FLOAT,
            wind FLOAT,
            time TEXT
        )
    """)

    # hae data
    cur.execute("""
        SELECT location, temp, wind, time
        FROM weather
        ORDER BY id DESC
        LIMIT 20
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # groupataan locationin mukaan
    data_by_location = {}

    for r in rows:
        location = r[0]

        try:
            dt = datetime.fromisoformat(r[3])
            dt = dt + timedelta(hours=3)
            formatted_time = dt.strftime("%d.%m.%Y %H:%M")
        except:
            formatted_time = r[3]

        entry = (r[1], r[2], formatted_time)

        if location not in data_by_location:
            data_by_location[location] = []

        data_by_location[location].append(entry)

    return render_template_string(
        """
        <h1>🌤 Weather</h1>

        {% for loc, items in data.items() %}
            <h2>{{ loc }}</h2>

            <h3>Latest</h3>
            <p>{{ items[0][0] }} °C, wind {{ items[0][1] }} m/s</p>

            <h3>History</h3>
            <ul>
            {% for r in items %}
                <li>{{ r[2] }} → {{ r[0] }}°C</li>
            {% endfor %}
            </ul>
        {% endfor %}
        """,
        data=data_by_location
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)