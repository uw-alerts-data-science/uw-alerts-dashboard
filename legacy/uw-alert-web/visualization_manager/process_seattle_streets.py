"""
Preprocessing functions of the seattle streets data
"""

import geopandas as gpd
import numpy as np


def filter_seattle_streets():
    """
    One time use module used to filter the Seattle_Streets.geojson
    file to only the streets that are in udistrict. Saves the output
    to '../data/SeattleGISData/udistrict_streets.geojson' The final
    geoJSON file has the following columns:
       1. UNITDESC: Structured description of the street location
       2. STNAME_ORD: Street segment name
       3. XSTRLO: Cross street at low end of segment
       4. XSTRHI: Cross street at high end of segment
       5. INTRLO: Description of the intersection location
          with cross street at low address  end of segment
       6. INTRHI: Description of the intersection location
          with cross street at high address  end of segment
       7. geometry: Geometry column
    """
    gdf = gpd.read_file("../data/SeattleGISData/Seattle_Streets.geojson")

    lon1 = []
    lon2 = []
    lat1 = []
    lat2 = []
    for street in gdf["geometry"]:
        coords = np.array(street.coords)
        lon1.append(coords[0, 0])
        lon2.append(coords[1, 0])
        lat1.append(coords[0, 1])
        lat2.append(coords[1, 1])

    gdf["lon1"] = lon1
    gdf["lon2"] = lon2
    gdf["lat1"] = lat1
    gdf["lat2"] = lat2

    longitude_bounds = (-122.2980, -122.3230)
    latitude_bounds = (47.67657, 47.6499)
    # Filtering for udistrict
    lon1_filt = (gdf["lon1"] > longitude_bounds[1]) & (
        gdf["lon1"] <= longitude_bounds[0]
    )
    lon2_filt = (gdf["lon2"] > longitude_bounds[1]) & (
        gdf["lon2"] <= longitude_bounds[0]
    )

    lat1_filt = (gdf["lat1"] > latitude_bounds[1]) & (gdf["lat1"] <= latitude_bounds[0])
    lat2_filt = (gdf["lat2"] > latitude_bounds[1]) & (gdf["lat2"] <= latitude_bounds[0])

    udist_gdf = gdf[lon1_filt & lat1_filt & lon2_filt & lat2_filt]

    relevant_cols = [
        "UNITDESC",
        "STNAME_ORD",
        "XSTRLO",
        "XSTRHI",
        "INTRLO",
        "INTRHI",
        "geometry",
    ]
    udist_gdf[relevant_cols].to_file(
        "../data/SeattleGISData/udistrict_streets_2.geojson", driver="GeoJSON"
    )


if __name__ == "__main__":
    filter_seattle_streets()
