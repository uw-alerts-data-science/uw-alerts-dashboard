"""
Name: Visualization Manager
What it does:
- Renders an interactive street map visualization
    - highlights specific streets of interest

- Includes details of uw alert events
inputs:
- street:
- alert_type:
- description:
- time:

outputs:
- interactive street visualization
"""

from datetime import datetime, timedelta
import os
import re
import pyproj
import folium
import math
from folium.plugins import HeatMap
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import nearest_points, transform


# pylint: disable=too-many-locals
def get_urgent_incidents(alerts_df, time_frame):
    """
    Retrieves and filters the uw_alerts_clean.csv
    for the incidents that occured today.

    Parameters
    ----------
    alerts_df: pd.DataFrame
        Pandas dataframe that contains columns
        ['Incident ID', 'Alert ID', 'Date', 'Report Time'].
        Result of reading in data/uw_alerts_clean.csv
    time_frame: int
        The time_frame cutoff in hours that specifies
        the number of hours before the current time to
        label alerts as 'urgent'.

    Returns
    -------
    urgent_incidents_df : Dataframe
        Pandas dataframe of the most urgent incidents
    """
    if not isinstance(alerts_df, type(pd.DataFrame())):
        raise TypeError("alerts_df must be of type pd.DataFrame")
    # Checking columns
    cols = ["Incident ID", "Alert ID", "Date", "Report Time"]
    for col in cols:
        if col not in alerts_df.columns.to_list():
            raise ValueError("Invalid alerts_df schema")

    # Step 1: Extract dataframe of alerts with Report time
    report_times_df = alerts_df[~alerts_df["Report Time"].isna()].copy()
    # Filter by time. Remove alerts beyond time cutoff
    report_times_df.loc[:, "report_datetime"] = pd.to_datetime(
        report_times_df["Date"] + " " + report_times_df["Report Time"]
    )
    # Extracting incidents that are within the timeframe
    urgent_datetime_alerts = report_times_df[
        report_times_df["report_datetime"]
        > datetime.now() - timedelta(hours=time_frame)
    ]
    incident_id_set1 = set(
        urgent_datetime_alerts["Incident ID"].drop_duplicates().to_list()
    )

    # Step 2: Keep incidents/alerts that occured on the same day, but have no Report time
    alerts_df["date"] = pd.to_datetime(alerts_df["Date"])

    # Filter by date
    # Remove alerts with no report time
    urgent_date_alerts = alerts_df[alerts_df["Report Time"].isna()]
    today_filter = urgent_date_alerts["date"].dt.date == datetime.now().date()
    urgent_date_alerts = urgent_date_alerts[today_filter]
    incident_id_set2 = set(
        urgent_date_alerts["Incident ID"].drop_duplicates().to_list()
    )

    # Step 3: Joining two sets into all urgent ids
    urgent_inc_ids = incident_id_set1 | incident_id_set2

    # Step 4: Filtering original dataframe to alerts with urgent incident ids
    urgent_alerts_df = alerts_df[alerts_df["Incident ID"].isin(urgent_inc_ids)]

    urgent_alerts_df = urgent_alerts_df.drop(columns="date")

    # No urgent alerts
    if len(urgent_alerts_df) == 0:
        return urgent_alerts_df

    # Step 5: Transform and filter the dataframe to only include the most
    # recent alert of each incident
    def combine_text(group):
        """
        Helper function to extract and combine
        Incident Alert column of the given group
        into a single row.

        Parameters
        ----------
        group : DataFrameGroupBy
            A collection of pandas dataframes
            where each dataframe is a single group
            with a unique Incident ID
        Returns
        -------
        row : dict
            A dictionary of the new values for the grouped
            dataframe
        """
        incident_df = group[1]
        col_names = ["Incident ID", "Alert ID", "Incident Alert"]
        incident_df = incident_df.sort_values(["Alert ID"], ascending=False)
        incident_id_value = incident_df["Incident ID"].iloc[0]
        alert_id_value = incident_df["Alert ID"].iloc[0]
        row = {
            col_names[0]: incident_id_value,
            col_names[1]: alert_id_value,
            col_names[2]: tuple(incident_df["Incident Alert"]),
        }
        return row

    groups = urgent_alerts_df[["Incident ID", "Alert ID", "Incident Alert"]].groupby(
        "Incident ID", as_index=False
    )

    data_list = []
    for group in groups:
        row = combine_text(group)
        data_list.append(row)

    incident_messages_df = pd.DataFrame(data_list)
    merged_df = pd.merge(
        urgent_alerts_df, incident_messages_df, how="right", on="Alert ID"
    )
    merged_df["Incident Alert"] = merged_df["Incident Alert_y"]
    merged_df = merged_df[
        [
            "Incident Category",
            "Incident Alert",
            "Nearest Address to Incident",
            "Date",
            "Report Time",
            "geometry",
        ]
    ]
    return merged_df


def filter_geodf(gdf, lat, lon, max_distance=10):
    """
    Given a latitude and longitude, returns a geopandas
    dataframe with the closest street objects within the
    given `max_distance` in meters.

    Parameters
    ----------
    gdf : Geopandas dataframe
        The geopandas dataframe with the streets
        data geometries
    lat : float
        latitude of the location of the alert
    long : float
        longitude of the location of the alert
    max_distance: int (default=10)
        The max distance of streets from the point
        in meters

    Returns
    -------
    gdf : Geopandas dataframe
        The filtered geopandas dataframe with
        only the streets that are within `max_distance`
        meters of the given `lat` and `lon` sorted by
        the distance column.
        Relevant Columns:
            - UNITDESC (object) : Full description of street
            - STNAME_ORD (object) : Street name
            - XSTRLO (object) : Street lower bound
            - XSTRHI (object) : Street upper bound
            - INTRLO (object) : Street lower intersection
            - INTRHI (object) : Street upper intersection
            - geometry (geometry) : shapely geometry object
            - distance (float64) : distance in meters from the point
    """

    if not isinstance(gdf, type(gpd.GeoDataFrame())):
        raise TypeError("gdf must be a geopandas.GeoDataFrame")
    if (lat > 90) | (lat < -90) | (lon < -180) | (lon > 180):
        raise ValueError("""invalid lat, lon combination, outside of valid bounds:\n
            lat:[-90,90]\n
            lon:[-180,180]""")

    # Point of interest
    alert_point = Point([lon, lat])

    # Define transformation
    project = pyproj.Transformer.from_proj(
        pyproj.Proj("EPSG:4326"), pyproj.Proj("EPSG:32610"), always_xy=True
    )

    # Projecting point
    projected_alert_point = transform(project.transform, alert_point)

    distances = []
    for street in gdf.geometry:
        # Projecting each linestring
        projected_street = transform(project.transform, street)
        # find the nearest points on the line and point geometries
        nearest_point_on_line, nearest_point_on_point = nearest_points(
            projected_street, projected_alert_point
        )
        # calculate the distance between the two nearest points
        distance = nearest_point_on_line.distance(nearest_point_on_point)
        distances.append(distance)

    gdf["distance"] = distances
    gdf = gdf.sort_values("distance")
    gdf = gdf[gdf["distance"] < max_distance]

    return gdf


# pylint: disable=too-many-locals
def get_folium_map(alert_df: pd.DataFrame):
    """
    Given information about alerts, return a rendered html leaflet map of the U-district area.

    Parameters
    ----------
    alert_df : pandas DataFrame
        Containing the urgent alerts as well as alert metadata
        Relevant Columns:
            - Incident Category
            - Incident Alert
            - geometry
            - Nearest Address to Incident
            - Date
            - Report Time

    Returns
    -------
    m_html : str
        A rendered html leaflet map to display on the web application.
    marker_dict: dict
        A dictionary of the marker metadata and map id.
        example:
            marker_dict['map_id'] = `map folium object id`
            marker_dict[marker_id] = (
                i, alert_categories[i], alert_report_time[i], incident_messages[i], date[i]
            )
    """
    # alert_df exceptions
    # pylint: disable=line-too-long
    if not isinstance(alert_df, pd.DataFrame):
        raise TypeError("alert_df must be a pandas DataFrame")
    for col in [
        "Incident Category",
        "Incident Alert",
        "Nearest Address to Incident",
        "geometry",
    ]:
        if col not in alert_df.columns:
            raise ValueError("""alert_df must have the following columns: Incident Category,
                                Incident Alert, Nearest Address to Incident, geometry""")
    # Display the U-District area
    dirname = os.path.dirname(__file__)
    udistrict_streets = os.path.join(
        dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
    )
    gdf = gpd.read_file(udistrict_streets)
    # pylint: disable=line-too-long
    mapbox_api_key = os.getenv("MAPBOX_API_KEY")
    tileset_id_str = "dark-v11"
    tilesize_pixels = "512"
    tile = f"https://api.mapbox.com/styles/v1/mapbox/{tileset_id_str}/tiles/{tilesize_pixels}/{{z}}/{{x}}/{{y}}@2x?access_token={mapbox_api_key}"
    alert_map = folium.Map(
        location=[47.66, -122.32], zoom_start=15, tiles=tile, attr="Maptiler Dark"
    )

    alert_coords = [list(loc["location"].values()) for loc in alert_df["geometry"]]
    alert_categories = list(alert_df["Incident Category"])
    alert_nearest_intersections = list(alert_df["Nearest Address to Incident"])
    incident_messages = list(alert_df["Incident Alert"])
    date = list(alert_df["Date"])
    alert_report_time = list(alert_df["Report Time"])

    marker_dict = {}
    # Plotting each alert on the map
    for i, coord in enumerate(alert_coords):
        # Display streets that are close to the alert
        #filtered_streets = filter_geodf(gdf, coord[0], coord[1])
        try:
            filtered_streets = filter_geodf(gdf, coord[0], coord[1])
        except ValueError:
            continue
        folium.Choropleth(
            geo_data=filtered_streets, line_weight=3, line_color="red", line_opacity=0.5
        ).add_to(alert_map)

        # Set a marker with an interactive popup
        iframe = folium.IFrame(
            "<center><h4 style=\"font-family: 'Noto Sans', sans-serif; margin-bottom:0;\">"
            + str(alert_categories[i])
            + "</h4><p style=\"font-family: 'Noto Sans', sans-serif; margin-top:4;\">"
            + str(alert_nearest_intersections[i])
            + "</p></center>",
            ratio="40%",
        )
        popup = folium.Popup(iframe, min_width=200, max_width=250)
        marker = folium.Marker(
            coord,
            popup=popup,
            icon=folium.Icon(color="red", icon="circle-exclamation", prefix="fa"),
        )
        # Add id to marker element
        marker.add_child(folium.Element(f'<div id="my_marker_{i}">My Marker</div>'))

        # Add marker to map
        marker.add_to(alert_map)

        # store marker metadata in marker_dict
        marker_id = marker.get_name()
        marker_dict[marker_id] = (
            i,
            alert_categories[i],
            alert_report_time[i],
            incident_messages[i],
            date[i],
        )

    # Store the map_id in marker_dict
    marker_dict["map_id"] = alert_map.get_name()

    # Create a heatmap layer for each alert

    alert_coords = [
        coord for coord in alert_coords
        if coord
        and len(coord) >= 2
        and coord[0] is not None
        and coord[1] is not None
        and not math.isnan(float(coord[0]))
        and not math.isnan(float(coord[1]))
    ]
    if alert_coords:
        HeatMap(alert_coords, radius=10, gradient={0: "lime", 0.5: "red"}).add_to(alert_map)
    m_html = alert_map.get_root().render()
    return (m_html, marker_dict)


def attach_marker_ids(m_html, marker_dict):
    """
     Takes in m_html and marker_dict output from
     get_folium map and updates the html to include
     onclick javascript methods to send marker_dict
     metadata to the alertcontainer.

     Parameters
     ----------
     m_html : str
         A rendered html leaflet map to display on the web application.
    marker_dict: dict
         A dictionary of the marker metadata and map id.
         example:
             marker_dict['map_id'] = `map folium object id`
             marker_dict[marker_id] = (
                 i, alert_categories[i], alert_report_time[i], incident_messages[i], date[i]
         )

     Returns
     -------
     updated_html : str
         A rendered html leaflet map with javascript methods that respond to
         on click interactions
     reindexed_marker_dict : dict
         A reindexed marker_dict where the keys are now the first element `i`
         for each marker instead of the marker id.
         example:
             marker_dict[i] = (
                 alert_categories[i], alert_report_time[i], incident_messages[i], date[i]
         )
    """
    updated_html = ""
    skip = 0
    lines = m_html.split("\n")
    for line in lines:
        if re.search(r"marker_.*=\sL.marker\(", line):
            marker_id = re.search(r"(marker_.*)\s=", line).group(1)
            # Generating script after marker found
            script = update_marker_definition(marker_id, marker_dict)
            updated_html += line + "\n"
            skip = 1
        elif skip == 1:
            updated_html += line
            updated_html += script
            skip = 3
        # Skipping the next two lines
        elif skip == 3:
            skip = 2
        elif skip == 2:
            skip = 0
        else:
            updated_html += line + "\n"

    # Reupdate marker_dict to change the keys
    reindexed_marker_dict = {}
    for key in marker_dict.keys():
        if key != "map_id":
            reindexed_marker_dict[str(marker_dict[key][0])] = (
                marker_dict[key][1],
                marker_dict[key][2],
                marker_dict[key][3],
                marker_dict[key][4],
            )
    return updated_html, reindexed_marker_dict


def update_marker_definition(marker_id, marker_dict):
    """
    Takes in a given marker id and marker dict
    with the marker metadata and returns a
    html and javascript string that updates each
    marker with an id and onclick functionality

    Parameters
    ----------
    marker_id : int
        An integer representing the unique marker id
    marker_dict: dict
        A reindexed marker_dict where the keys are now the first element `i`
        for each marker instead of the marker id.
        example:
            marker_dict[i] = (
                alert_categories[i], alert_report_time[i], incident_messages[i], date[i]
        )

    Returns
    -------
    new_script : str
        A string of html and javascript that updates each
        marker in the original map_html to include an id
        and onclick functionality.
    """
    # Extracting metadata
    element_id, category, report_time, incident_messages, date = marker_dict[marker_id]
    map_id = marker_dict["map_id"]
    # Building html alert for left panel
    if isinstance(report_time, str):
        if len(report_time.split(":")) == 3:
            # Convert time string to datetime object
            time_obj = datetime.strptime(report_time, "%H:%M:%S")
            # Convert datetime object to non-military format string
            hour = str(int(datetime.strftime(time_obj, "%I")))
            report_time_str = hour + datetime.strftime(time_obj, ":%M %p")
    else:
        report_time_str = ""

    html_string = f"""
            <h2>{category} - {date} {report_time_str}</h2><br>
    """
    for i, alert_message in enumerate(incident_messages):
        if i == 0:
            alert_message_html = f"""
            <p>{alert_message}</p><br>
            """
        else:
            alert_message_html = f"""
            <div style="background-color: #2C2C2C; color: #2C2C2C; height: 2px; width: 100%; margin: 0;"></div><br>
            <p>{alert_message}</p><br>
            """
        html_string += alert_message_html
    new_script = f"""
                {"{id:"} {element_id}{"}"}
            ).addTo({map_id});

            {marker_id}.on('click', function() {"{"}
            const markerId = this.options.id;
            let alertObj = JSON.parse(localStorage.getItem("alertDescs"));
            // Get a reference to the element in the parent document
            var alertFrame = parent.document.getElementById('alertcontainer');
            var htmlString = `
            {html_string}
            `;
            alertFrame.innerHTML = htmlString
            {"}"});
    """
    return new_script
