"""
Name: uw-alert-web.py
Initializes a web application for UW Alerts Visualization
A python module that contains all the server side functions that allow
for communication between the front end (html files) to the backend (.py files).
It handles requests from the frontend to update the map with new information.
"""

import ast
import io
import os
import json
import subprocess
import sys
import pandas as pd
import openai
import googlemaps
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

# Our modules
# pylint: disable="import-error"
from .visualization_manager.visualization_manager import get_folium_map
from .visualization_manager.visualization_manager import (
    get_urgent_incidents,
    attach_marker_ids,
)
from .parse_uw_alerts import parse_uw_alerts
from . import db

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.default_charset = "utf-8"


@app.route("/")
def render_home_page():
    """
    Renders the home page using home.html using
    the database. Displays
    current urgent alerts within the specified time_frame

    Returns
    -------
    HTTP response containing html content that is
    sent to front end in flask
    """
    alert_df = db.query_incidents_as_dataframe(hours=24 * 7)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("home.html", map_html=updated_map, alert_dict=marker_json)


@app.route("/redirect_to_home", methods=["POST"])
def redirect_to_home():
    """
    Creates a route that redirects back to the home page

    Returns
    -------
    HTTP response containing html content that is
    sent to front end in flask
    """
    return redirect(url_for("render_home_page"))


@app.route("/demo", methods=["GET"])
def render_demo_page():
    """
    Renders the demo page using demo.html using
    the database. Allows
    for user input to add additional alerts Displays
    current urgent alerts within the specified time_frame
    Purely for demo purposes.

    Returns
    -------
    HTTP response containing demo page html content that is
    sent to front end in flask
    """
    alert_df = db.query_incidents_as_dataframe(hours=24)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("demo.html", map_html=updated_map, alert_dict=marker_json)


@app.route("/past", methods=["GET"])
def render_past_page():
    """
    Renders the past page using past.html using
    the database. Displays
    all past uw alerts.

    Returns
    -------
    HTTP response containing past page html content that is
    sent to front end in flask
    """
    alert_df = db.query_incidents_as_dataframe()
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("past.html", map_html=updated_map, alert_dict=marker_json)


@app.route("/about", methods=["GET"])
def about():
    """
    Creates the Flask route for the about page

    Returns
    -------
    HTTP response containing html content that is
    sent to front end in flask
    """
    return render_template("/about.html")


# pylint: disable=too-many-locals
@app.route("/update_map", methods=["POST"])
def update_map():
    """
    Takes the text input from demo page
    through flask and rerenders the demo page
    with the new alerts.

    Returns
    -------
    HTTP response containing demo page html content that is
    sent to front end in flask
    """
    # Parsing
    load_dotenv("../env")
    openai.api_key = os.getenv("OPENAI_API_KEY")
    uw_alert_filepath = "../data/uw_alerts_clean.csv"
    uw_alerts = pd.read_csv(uw_alert_filepath, index_col=False)
    new_data = request.form["text-input"]
    buf = io.StringIO(new_data)
    gpt_output = parse_uw_alerts.prompt_gpt(buf.readlines(), return_alert_type=True)
    google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gmaps = googlemaps.Client(key=google_maps_api_key)
    cleaned_gpt_output = parse_uw_alerts.generate_ids(
        uw_alert_filepath, gpt_table=gpt_output[0], alert_type=gpt_output[1]
    )
    gpt_table = parse_uw_alerts.clean_gpt_output(
        gpt_output=cleaned_gpt_output, gmaps_client=gmaps
    )
    uw_alerts = pd.concat([gpt_table, uw_alerts], ignore_index=True)
    uw_alerts.to_csv(uw_alert_filepath, index=False)
    # send cleaned csv into viz manager
    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, "../data/uw_alerts_clean.csv")
    alert_df = pd.read_csv(filename, converters={"geometry": ast.literal_eval})
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=24)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("demo.html", map_html=updated_map, alert_dict=marker_json)


@app.route("/fully_update", methods=["GET"])
def fully_update():
    """
    Runs the scraper agent to fetch new alerts, then renders
    the home page with the latest data from the database.

    Returns
    -------
    Fully rendered HTML page sent to the front end.
    """
    result = subprocess.run(
        [sys.executable, "-m", "scraper.scraper_agent"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        app.logger.error("scraper_agent failed: %s", result.stderr)
        return "Scraper failed. Check server logs for details.", 500

    alert_df = db.query_incidents_as_dataframe(hours=24 * 7)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("home.html", map_html=updated_map, alert_dict=marker_json)


if __name__ == "__main__":
    app.run(debug=True)
