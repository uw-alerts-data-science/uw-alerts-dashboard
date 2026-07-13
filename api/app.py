from flask import Flask, jsonify
from flask_cors import CORS

from db import get_connection


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
    query = """
        SELECT
          i.id,
          COALESCE(NULLIF(a.summary, ''), i.category || ' Alert') AS title,
          i.category,
          COALESCE(i.google_address, i.nearest_address) AS address,
          i.lat::float AS latitude,
          i.lng::float AS longitude,
          COALESCE(a.reported_at, i.first_reported_at, i.occurred_at, i.created_at) AS reported_at
        FROM incidents i
        LEFT JOIN LATERAL (
          SELECT *
          FROM alerts a
          WHERE a.incident_id = i.id
          ORDER BY a.reported_at DESC NULLS LAST, a.created_at DESC
          LIMIT 1
        ) a ON true
        WHERE i.lat IS NOT NULL
          AND i.lng IS NOT NULL
        ORDER BY reported_at DESC NULLS LAST
        LIMIT 100;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    alerts = [
        {
            "id": row["id"],
            "title": row["title"],
            "category": row["category"],
            "address": row["address"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "reportedAt": row["reported_at"].isoformat()
            if row["reported_at"]
            else None,
        }
        for row in rows
    ]

    return jsonify({"alerts": alerts})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)