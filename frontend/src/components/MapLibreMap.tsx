"use client";

import { useEffect, useRef } from "react";
import type { FeatureCollection, Point } from "geojson";
import maplibregl, { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { mockAlerts } from "../lib/mockAlerts";

function getCategoryClass(category: string) {
  const normalized = category.toLowerCase();

  if (normalized.includes("robbery")) return "robbery";
  if (normalized.includes("suspicious")) return "suspicious";
  if (normalized.includes("safety")) return "safety";

  return "default";
}

function buildAlertsGeoJson(): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features: mockAlerts.map((alert) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [alert.longitude, alert.latitude],
      },
      properties: {
        id: alert.id,
        title: alert.title,
        category: alert.category,
        categoryClass: getCategoryClass(alert.category),
        address: alert.address,
        reportedAt: alert.reportedAt,
      },
    })),
  };
}

export default function MapLibreMap() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
      center: [-122.3035, 47.6553],
      zoom: 12,
    });

    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", () => {
      map.addSource("alerts", {
        type: "geojson",
        data: buildAlertsGeoJson(),
        cluster: true,
        clusterMaxZoom: 15,
        clusterRadius: 80,
      });

    map.addLayer({
      id: "alert-clusters",
      type: "circle",
      source: "alerts",
      filter: ["has", "point_count"],
      paint: {
        "circle-color": "#7c3aed",
        "circle-radius": [
          "step",
          ["get", "point_count"],
          22,
          3,
          28,
          6,
          34,
        ],
        "circle-stroke-width": 3,
        "circle-stroke-color": "#ffffff",
      },
    });

      map.addLayer({
        id: "alert-cluster-count",
        type: "symbol",
        source: "alerts",
        filter: ["has", "point_count"],
        layout: {
          "text-field": "{point_count_abbreviated}",
          "text-size": 14,
          "text-font": ["Noto Sans Bold"],
        },
        paint: {
          "text-color": "#ffffff",
        },
      });

      map.addLayer({
        id: "alert-unclustered",
        type: "circle",
        source: "alerts",
        filter: ["!", ["has", "point_count"]],
        paint: {
          "circle-color": [
            "match",
            ["get", "categoryClass"],
            "robbery",
            "#d7263d",
            "suspicious",
            "#f59e0b",
            "safety",
            "#2563eb",
            "#6b7280",
          ],
          "circle-radius": 10,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on("click", "alert-clusters", async (event: MapMouseEvent) => {
        const features = map.queryRenderedFeatures(event.point, {
          layers: ["alert-clusters"],
        });

        const cluster = features[0];

        if (!cluster || !cluster.properties) return;

        const clusterId = cluster.properties.cluster_id;
        const source = map.getSource("alerts") as GeoJSONSource;
        const zoom = await source.getClusterExpansionZoom(clusterId);

        const geometry = cluster.geometry;

        if (geometry.type !== "Point") return;

        map.easeTo({
          center: geometry.coordinates as [number, number],
          zoom,
        });
      });

    map.on("click", "alert-unclustered", (event: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(event.point, {
        layers: ["alert-unclustered"],
      });
  
      const feature = features[0];
  
      if (!feature || feature.geometry.type !== "Point") return;
  
      const coordinates = feature.geometry.coordinates as [number, number];
      const properties = feature.properties;
  
      if (!properties) return;
  
      openAlertPopup({
        coordinates,
        title: String(properties.title),
        category: String(properties.category),
        address: String(properties.address),
        reportedAt: String(properties.reportedAt),
      });
    });

      map.on("mouseenter", "alert-clusters", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "alert-clusters", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("mouseenter", "alert-unclustered", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "alert-unclustered", () => {
        map.getCanvas().style.cursor = "";
      });

      map.resize();
    });

    return () => {
      popupRef.current?.remove();
      popupRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  function openAlertPopup({
    coordinates,
    title,
    category,
    address,
    reportedAt,
  }: {
    coordinates: [number, number];
    title: string;
    category: string;
    address: string;
    reportedAt: string;
  }) {
    const map = mapRef.current;

    if (!map) return;

    popupRef.current?.remove();

    popupRef.current = new maplibregl.Popup({ offset: 18 })
      .setLngLat(coordinates)
      .setHTML(`
        <strong>${title}</strong><br />
        <span>${category}</span><br />
        <span>${address}</span><br />
        <small>${reportedAt}</small>
      `)
      .addTo(map);
  }

  function zoomToAlert(alertId: number) {
    const alert = mockAlerts.find((item) => item.id === alertId);
    const map = mapRef.current;

    if (!alert || !map) return;

    const coordinates: [number, number] = [alert.longitude, alert.latitude];

    map.flyTo({
      center: coordinates,
      zoom: 16,
      speed: 1.2,
      curve: 1.4,
      essential: true,
    });

    map.once("moveend", () => {
      openAlertPopup({
        coordinates,
        title: alert.title,
        category: alert.category,
        address: alert.address,
        reportedAt: alert.reportedAt,
      });
    });
  }

  return (
    <div className="map-layout">
      <aside className="alert-sidebar">
        <h2>Mock Alerts</h2>

        <div className="map-legend">
          <div>
            <span className="legend-dot category-robbery" />
            Robbery
          </div>
          <div>
            <span className="legend-dot category-suspicious" />
            Suspicious Activity
          </div>
          <div>
            <span className="legend-dot category-safety" />
            Safety Notice
          </div>
        </div>

        <div className="alert-list">
          {mockAlerts.map((alert) => (
            <button
              key={alert.id}
              className="alert-card"
              onClick={() => zoomToAlert(alert.id)}
            >
              <strong>{alert.title}</strong>
              <span className={`alert-category category-${getCategoryClass(alert.category)}`}>
                {alert.category}
              </span>
              <small>{alert.address}</small>
            </button>
          ))}
        </div>
      </aside>

      <div ref={mapContainer} className="map-container" />
    </div>
  );
}