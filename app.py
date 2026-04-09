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

    # varmista että taulu on olemassa
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id SERIAL PRIMARY KEY,
            temp FLOAT,
            wind FLOAT,
            time TEXT
        )
    """)

    # hae data
    cur.execute("SELECT temp, wind, time FROM weather ORDER BY id DESC LIMIT 10")
    rows = cur.fetchall()

    converted_rows = []

    for r in rows:
        try:
            dt = datetime.fromisoformat(r[2])
            dt = dt + timedelta(hours=3) 
            formatted = dt.strftime("%d.%m.%Y %H:%M")
        except:
            formatted = r[2]

        converted_rows.append((r[0], r[1], formatted))

    cur.close()
    conn.close()

    latest = converted_rows[0] if converted_rows else (None, None, None)

    return render_template_string(
        """
        <h1>🌤 Weather in Oulu</h1>

        <h2>Latest</h2>
        <p>{{ latest[0] }} °C, wind {{ latest[1] }} m/s</p>

        <h2>History</h2>
        <ul>
        {% for r in history %}
            <li>{{ r[2] }} → {{ r[0] }}°C</li>
        {% endfor %}
        </ul>
        """,
        latest=latest,
        history=converted_rows,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)