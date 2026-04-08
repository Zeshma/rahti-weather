from flask import Flask, render_template_string
import requests

app = Flask(__name__)

HTML = """
<h1>Weather in Oulu</h1>

<p>Temperature: {{ temp }} °C</p>
<p>Wind Speed: {{ wind }} m/s</p>
<p>Time: {{ time }}</p>
"""

@app.route("/")
def home():
    url = "https://api.open-meteo.com/v1/forecast?latitude=65.01&longitude=25.47&current_weather=true"
    data = requests.get(url).json()

    weather = data.get("current_weather", {})

    return render_template_string(
        HTML,
        temp=weather.get("temperature"),
        wind=weather.get("windspeed"),
        time=weather.get("time"),
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)