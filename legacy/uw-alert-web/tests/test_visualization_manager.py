"""
Tests for visualization_manager.py
"""

import unittest
import ast
import os
from datetime import datetime, timedelta

import geopandas as gpd
import pandas as pd
import pandas.testing as pdt
import numpy as np

# pylint: disable=import-error
from visualization_manager.visualization_manager import (
    filter_geodf,
    get_folium_map,
    get_urgent_incidents,
    attach_marker_ids,
)


class TestGetUrgentAlerts(unittest.TestCase):
    """
    Tests get_urgent_alerts method in
    visualization_manager.py.
    """

    # Smoke test
    def test_smoke(self):
        """
        Smoke test for get_urgent_alerts function
        """
        flag = True
        try:
            dirname = os.path.dirname(__file__)
            file_path = os.path.join(dirname, "../../data/uw_alerts_clean.csv")
            alerts_df = pd.read_csv(file_path)
            get_urgent_incidents(alerts_df, time_frame=4)
        except ValueError:
            flag = False
        self.assertTrue(flag)

    # One shot tests
    def test_time_frame_cutoff(self):
        """
        get_urgent incidents should filter the
        incidents dataframe based on whether the
        date and report time was within the timeframe of
        4 hours before the current time.
        """
        today = datetime.today()
        two_days_ago = today - timedelta(days=2)
        cols = [
            "Alert ID",
            "Incident ID",
            "Date",
            "Report Time",
            "Incident Alert",
            "Incident Category",
            "Nearest Address to Incident",
            "geometry",
        ]
        data = [
            [
                "6",
                "2",
                today.strftime("%m/%d/%Y"),
                today.strftime("%H:%M"),
                "Update 3",
                None,
                None,
                None,
            ],
            [
                "5",
                "2",
                (today - timedelta(hours=3)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=3)).strftime("%H:%M"),
                "Update 2",
                None,
                None,
                None,
            ],
            [
                "4",
                "2",
                (today - timedelta(hours=5)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=5)).strftime("%H:%M"),
                "Update 1",
                None,
                None,
                None,
            ],
            [
                "3",
                "2",
                (today - timedelta(hours=6)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=6)).strftime("%H:%M"),
                "Original Post",
                None,
                None,
                None,
            ],
            [
                "2",
                "4",
                (today - timedelta(hours=10)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=10)).strftime("%H:%M"),
                "Test Alert",
                None,
                None,
                None,
            ],
            [
                "1",
                "1",
                two_days_ago.strftime("%m/%d/%Y"),
                two_days_ago.strftime("%H:%M"),
                "Test Alert",
                None,
                None,
                None,
            ],
        ]

        expected_cols = [
            "Incident Category",
            "Incident Alert",
            "Nearest Address to Incident",
            "Date",
            "Report Time",
            "geometry",
        ]
        expected = [
            [
                None,
                ("Update 3", "Update 2", "Update 1", "Original Post"),
                None,
                today.strftime("%m/%d/%Y"),
                today.strftime("%H:%M"),
                None,
            ]
        ]
        test_data = pd.DataFrame(data, columns=cols)
        expected_df = pd.DataFrame(expected, columns=expected_cols)
        result = get_urgent_incidents(alerts_df=test_data, time_frame=4)
        pdt.assert_frame_equal(expected_df, result)

    def test_missing_report_times(self):
        """
        get_urgent_incidents should filter based
        on report time and date first, but if there
        is no report time, it should take any incidents
        that occured that day.
        """
        today = datetime.today()
        two_days_ago = today - timedelta(days=2)
        cols = [
            "Alert ID",
            "Incident ID",
            "Date",
            "Report Time",
            "Incident Alert",
            "Incident Category",
            "Nearest Address to Incident",
            "geometry",
        ]
        data = [
            [
                "6",
                "2",
                today.strftime("%m/%d/%Y"),
                today.strftime("%H:%M"),
                "Update 3",
                None,
                None,
                None,
            ],
            [
                "5",
                "2",
                (today - timedelta(hours=3)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=3)).strftime("%H:%M"),
                "Update 2",
                None,
                None,
                None,
            ],
            [
                "4",
                "2",
                (today - timedelta(hours=5)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=5)).strftime("%H:%M"),
                "Update 1",
                None,
                None,
                None,
            ],
            [
                "3",
                "2",
                (today - timedelta(hours=6)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=6)).strftime("%H:%M"),
                "Original Post",
                None,
                None,
                None,
            ],
            [
                "2",
                "4",
                today.strftime("%m/%d/%Y"),
                None,
                "Test Alert",
                None,
                None,
                None,
            ],
            [
                "1",
                "1",
                two_days_ago.strftime("%m/%d/%Y"),
                two_days_ago.strftime("%H:%M"),
                "Test Alert",
                None,
                None,
                None,
            ],
        ]

        expected_cols = [
            "Incident Category",
            "Incident Alert",
            "Nearest Address to Incident",
            "Date",
            "Report Time",
            "geometry",
        ]
        expected = [
            [
                None,
                ("Update 3", "Update 2", "Update 1", "Original Post"),
                None,
                today.strftime("%m/%d/%Y"),
                today.strftime("%H:%M"),
                None,
            ],
            [None, ("Test Alert",), None, today.strftime("%m/%d/%Y"), None, None],
        ]
        test_data = pd.DataFrame(data, columns=cols)
        expected_df = pd.DataFrame(expected, columns=expected_cols)
        result = get_urgent_incidents(alerts_df=test_data, time_frame=4)
        pdt.assert_frame_equal(expected_df, result)

    def test_no_urgent_incidents(self):
        """
        Tests the case where all incidents are
        outside of the timeframe, so get_urgent_incidents
        should return no incidents.
        """
        today = datetime.today()
        two_days_ago = today - timedelta(days=2)
        cols = ["Alert ID", "Incident ID", "Date", "Report Time", "Keep"]
        data = [
            [
                "1",
                "1",
                two_days_ago.strftime("%m/%d/%Y"),
                two_days_ago.strftime("%H:%M"),
                False,
            ],
            [
                "2",
                "2",
                (today - timedelta(hours=5)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=5)).strftime("%H:%M"),
                False,
            ],
            [
                "3",
                "3",
                (today - timedelta(hours=6)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=6)).strftime("%H:%M"),
                False,
            ],
            [
                "4",
                "4",
                (today - timedelta(hours=10)).strftime("%m/%d/%Y"),
                (today - timedelta(hours=10)).strftime("%H:%M"),
                False,
            ],
        ]
        test_data = pd.DataFrame(data, columns=cols)
        expected = test_data[test_data["Keep"]]
        result = get_urgent_incidents(alerts_df=test_data, time_frame=4)
        pdt.assert_frame_equal(expected, result)

    # Edge cases
    def test_dataframe_schema(self):
        """
        Testing get_urgent_incidents, raising
        ValueError if essential columns are missing.
        """
        cols = ["Alert ID", "Incident ID", "Date"]
        data = [["1", "2", "3/4/23"]]
        test_data = pd.DataFrame(data, columns=cols)
        with self.assertRaises(ValueError):
            get_urgent_incidents(alerts_df=test_data, time_frame=4)

    def test_dataframe_input(self):
        """
        Testing get_urgent_incidents alerts_df
        input parameter is type DataFrame
        """
        with self.assertRaises(TypeError):
            get_urgent_incidents(alerts_df=[], time_frame=4)


class TestFilterGeoDF(unittest.TestCase):
    """
    Tests methods for filter_geodf function
    in visualization_manager.py
    """

    # Smoke tests
    def test_smoke(self):
        """
        Smoke test for filter_geodf
        """
        flag = True
        try:
            dirname = os.path.dirname(__file__)
            file_path = os.path.join(
                dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
            )
            gdf = gpd.read_file(file_path)
            filter_geodf(gdf, lat=10.0, lon=15)
        except ValueError:
            flag = False
        self.assertTrue(flag)

    # One shot tests
    def test_coord_on_street1(self):
        """
        One shot test for coordinates on
        42nd street between 9th and Roosevelt
        """
        point = [47.657489, -122.318281]
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(
            dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
        )
        gdf = gpd.read_file(file_path)
        test_gdf = filter_geodf(gdf, lat=point[0], lon=point[1])
        self.assertEqual(len(test_gdf), 1)
        self.assertEqual(
            test_gdf["UNITDESC"].iloc[0],
            "NE 42ND ST BETWEEN 9TH AVE NE AND ROOSEVELT S WAY NE",
        )

    def test_coord_on_street2(self):
        """
        One shot test for coordinates on
        8th Ave between 43rd and 45th
        """
        point = [47.660443, -122.319788]
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(
            dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
        )
        gdf = gpd.read_file(file_path)
        test_gdf = filter_geodf(gdf, lat=point[0], lon=point[1])
        self.assertEqual(len(test_gdf), 1)
        self.assertEqual(
            test_gdf["UNITDESC"].iloc[0],
            "8TH AVE NE BETWEEN NE 43RD ST AND NE 45TH W ST",
        )

    def test_intersection(self):
        """
        One shot test for 45th and Brooklyn
        intersection. Should return dataframe with 4 streets
        """
        point = [47.66131221275655, -122.31431884850726]
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(
            dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
        )
        gdf = gpd.read_file(file_path)
        test_gdf = filter_geodf(gdf, lat=point[0], lon=point[1])

        streets = [
            "NE 45TH ST BETWEEN 12TH AVE NE AND BROOKLYN AVE NE",
            "BROOKLYN AVE NE BETWEEN NE 45TH ST AND NE 47TH ST",
            "BROOKLYN AVE NE BETWEEN NE 43RD ST AND NE 45TH ST",
            "NE 45TH ST BETWEEN BROOKLYN AVE NE AND UNIVERSITY WAY NE",
        ]
        test_streets = list(test_gdf["UNITDESC"])
        self.assertEqual(len(test_gdf), 4)
        for street in test_streets:
            self.assertTrue(street in streets)

    # Edge case tests
    def test_gdf_input_type(self):
        """
        Edge case test to check that gdf is a geopandas
        dataframe
        """
        test_cases = ["String", {}, np.array([3, 2, 2]), 34]
        for gdf in test_cases:
            with self.assertRaises(TypeError):
                filter_geodf(gdf, lat=33.2, lon=22.1)

    def test_valid_lon_lat(self):
        """
        Edge case test to check that invalid longitude, latitude
        values raise a ValueError
        """
        test_cases = [[-90.4, -130], [22, 190], [-180, -200]]
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(
            dirname, "../../data/SeattleGISData/udistrict_streets.geojson"
        )
        gdf = gpd.read_file(file_path)
        for point in test_cases:
            with self.assertRaises(ValueError):
                filter_geodf(gdf, lat=point[0], lon=point[1])


class TestGetFoliumMap(unittest.TestCase):
    """
    Tests methods for get_folium_map function
    in visualization_manager.py
    """

    # Smoke test
    def test_smoke(self):
        """
        Smoke test for filter_geodf
        """
        flag = True
        try:
            dirname = os.path.dirname(__file__)
            file_path = os.path.join(dirname, "../../data/uw_alerts_clean.csv")
            alert_df = pd.read_csv(
                file_path, converters={"geometry": ast.literal_eval}
            ).head()
            get_folium_map(alert_df)
        except ValueError:
            flag = False
        self.assertTrue(flag)

    # Edge case tests
    def test_not_pandas_dataframe(self):
        """
        Edge case test to check that alert_df is a pandas dataframe
        """
        test_cases = ["String", {}, np.array([3, 2, 2]), 34]
        for alert_df in test_cases:
            with self.assertRaises(TypeError):
                get_folium_map(alert_df)

    def test_dataframe_has_necessary_columns(self):
        """
        Edge case test to check that alert_df has the necessary columns
        """

        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/uw_alerts_clean.csv")
        alert_df = (
            pd.read_csv(file_path, converters={"geometry": ast.literal_eval})
            .head()
            .drop("geometry", axis=1)
        )
        with self.assertRaises(ValueError):
            get_folium_map(alert_df)


class TestAttachMarkerIDs(unittest.TestCase):
    """
    Tests methods for attach_marker_ids function
    in visualization_manager.py
    """

    # oneshot test
    def test_simple_html(self):
        """
        Tests the attach_marker_id function
        for a single marker case where we
        need to update the html to include a marker
        id and javascript onclick functionalities.
        """
        self.maxDiff = None
        m_html = """
        function geo_json_66a89e6bf89424e72991ded6eb5bac69_add (data) {
            geo_json_66a89e6bf89424e72991ded6eb5bac69
                .addData(data)
                .addTo(choropleth_5961c55f453556107abef4283990ea7a);
        }
            geo_json_66a89e6bf89424e72991ded6eb5bac69_add({"bbox": [NaN, NaN, NaN, NaN], "features": [], "type": "FeatureCollection"});

        
    
            var marker_83890b04aaf785c57736be66c43231bb = L.marker(
                [47.6604329, -122.3115365],
                {}
            ).addTo(map_8986a6e632750fefa0097972e041860a);
        
        """
        marker_dict = {
            "map_id": "map_8986a6e632750fefa0097972e041860a",
            "marker_83890b04aaf785c57736be66c43231bb": (
                2,
                "Stabbing",
                "10:03:00",
                (
                    "UPDATE (10:03 a.m.): A stabbing investigation is ongoing",
                    "ORIGINAL POST: Stabbing occurred",
                ),
                "9/4/18",
            ),
        }
        expected_html = """
        function geo_json_66a89e6bf89424e72991ded6eb5bac69_add (data) {
            geo_json_66a89e6bf89424e72991ded6eb5bac69
                .addData(data)
                .addTo(choropleth_5961c55f453556107abef4283990ea7a);
        }
            geo_json_66a89e6bf89424e72991ded6eb5bac69_add({"bbox": [NaN, NaN, NaN, NaN], "features": [], "type": "FeatureCollection"});

        
    
            var marker_83890b04aaf785c57736be66c43231bb = L.marker(
                [47.6604329, -122.3115365],
                {id: 2}
            ).addTo(map_8986a6e632750fefa0097972e041860a);

            marker_83890b04aaf785c57736be66c43231bb.on('click', function() {
            const markerId = this.options.id;
            let alertObj = JSON.parse(localStorage.getItem("alertDescs"));
            // Get a reference to the element in the parent document
            var alertFrame = parent.document.getElementById('alertcontainer');
            var htmlString = `
            
            <h2>Stabbing - 9/4/18 10:03 AM</h2><br>
    
            <p>UPDATE (10:03 a.m.): A stabbing investigation is ongoing</p><br>
            
            <div style="background-color: #2C2C2C; color: #2C2C2C; height: 2px; width: 100%; margin: 0;"></div><br>
            <p>ORIGINAL POST: Stabbing occurred</p><br>
            
            `;
            alertFrame.innerHTML = htmlString
            });\n            \n        \n"""
        expected_marker_dict = {
            "2": (
                "Stabbing",
                "10:03:00",
                (
                    "UPDATE (10:03 a.m.): A stabbing investigation is ongoing",
                    "ORIGINAL POST: Stabbing occurred",
                ),
                "9/4/18",
            )
        }
        updated_html, reindexed_marker_dict = attach_marker_ids(m_html, marker_dict)
        self.assertEqual(expected_html, updated_html)
        self.assertEqual(expected_marker_dict, reindexed_marker_dict)


if __name__ == "__main__":
    unittest.main()
