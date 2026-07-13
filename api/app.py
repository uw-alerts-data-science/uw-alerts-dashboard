from flask import Flask, jsonify
from flask_cors import CORS


app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
            ]
        }
    },
)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/alerts")
def get_alerts():
    return jsonify(
        {
            "alerts": [
                {
                    "id": 1,
                    "title": "Test UW Alert",
                    "category": "Safety Notice",
                    "address": "University of Washington, Seattle, WA",
                    "latitude": 47.6553,
                    "longitude": -122.3035,
                    "reportedAt": "2026-07-09T12:00:00Z",
                },
                {
                    "id": 2,
                    "title": "Suspicious Activity",
                    "category": "Suspicious Activity",
                    "address": "University District, Seattle, WA",
                    "latitude": 47.6614,
                    "longitude": -122.3132,
                    "reportedAt": "2026-07-09T12:15:00Z",
                },
                {
                    "id": 3,
                    "title": "Robbery Report",
                    "category": "Robbery",
                    "address": "Near UW Medical Center",
                    "latitude": 47.6502,
                    "longitude": -122.3078,
                    "reportedAt": "2026-07-09T12:30:00Z",
                },
            ]
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)