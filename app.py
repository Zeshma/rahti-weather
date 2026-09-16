from flask import Flask, render_template_string, jsonify, abort
import urllib.request
import json
import psycopg2
from datetime import datetime, timedelta

import config

app = Flask(__name__)

def get_connection():
    return psycopg2.connect(**config.db_connection_kwargs())


def fetch_health(url, timeout=3):
    """Fetch a health endpoint, return (status_dict, http_status)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode()), resp.status
    except Exception as e:
        return {"status": "unreachable", "error": str(e)}, 503

@app.route("/status")
def status_page():
    """Show the health of all components on a single page."""
    if not config.STATUS_PAGE_ENABLED:
        abort(404)
    components = [
        ("Web (this pod)", "http://localhost:8080/health"),
        ("Producer", "http://localhost:8081/health"),
        ("Consumer", "http://rahti-weather-consumer:8082/health"),
    ]
    results = []
    for name, url in components:
        data, http_status = fetch_health(url)
        results.append({
            "name": name,
            "status": data.get("status", "unknown"),
            "details": data,
            "http_status": http_status,
        })
    all_healthy = all(r["status"] == "healthy" for r in results)
    return render_template_string(
        """
        <html>
        <head>
            <meta http-equiv="refresh" content="10">
            <title>Weather - Status</title>
            <style>
                body { font-family: sans-serif; margin: 2em; }
                h1 { margin-bottom: 1em; }
                .component {
                    border: 1px solid #ccc; border-radius: 8px;
                    padding: 1em 1.5em; margin-bottom: 1em;
                    display: flex; align-items: center; gap: 1em;
                }
                .badge {
                    display: inline-block; padding: 4px 12px;
                    border-radius: 12px; font-weight: bold;
                    color: #fff; min-width: 80px; text-align: center;
                }
                .healthy { background: #2e7d32; }
                .unhealthy, .unreachable { background: #c62828; }
                .unknown { background: #757575; }
                .details { color: #666; font-size: 0.9em; margin-left: auto; }
                .overall { font-size: 1.2em; margin-bottom: 1.5em; }
                .footer { color: #999; font-size: 0.8em; margin-top: 2em; }
            </style>
        </head>
        <body>
            <h1>Weather - System Status</h1>
            <p class="overall">
                Overall:
                <span class="badge {{ "healthy" if all_healthy else "unhealthy" }}">
                    {{ "ALL HEALTHY" if all_healthy else "ISSUES DETECTED" }}
                </span>
            </p>
            {% for r in results %}
            <div class="component">
                <span class="badge {{ r.status }}">{{ r.status | upper }}</span>
                <strong>{{ r.name }}</strong>
                <span class="details">{{ r.details }}</span>
            </div>
            {% endfor %}
            <p class="footer">Auto-refreshes every 10 seconds.</p>
        </body>
        </html>
        """,
        results=results,
        all_healthy=all_healthy,
    )


@app.route("/health")
def health_check():
    try:
        # Check database connectivity
        conn = get_connection()
        cur = conn.cursor()

        # Simple query to test database
        cur.execute("SELECT 1")
        result = cur.fetchone()

        cur.close()
        conn.close()

        if result == (1,):
            return jsonify({
                "status": "healthy",
                "database": "connected",
                "timestamp": datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                "status": "unhealthy",
                "database": "unexpected_response",
                "timestamp": datetime.now().isoformat()
            }), 500

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

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
        <hr>
        {% if status_page_enabled %}
        <p><a href="/status">System Status</a></p>
        {% endif %}
        """,
        data=data_by_location,
        status_page_enabled=config.STATUS_PAGE_ENABLED
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.WEB_PORT)