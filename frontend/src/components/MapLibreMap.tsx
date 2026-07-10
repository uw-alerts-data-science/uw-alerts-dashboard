"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FeatureCollection, Point } from "geojson";
import maplibregl, { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { mockAlerts, type AlertMarker } from "../lib/mockAlerts";

const ALERT_CATEGORIES = [
  "Robbery",
  "Suspicious Activity",
  "Safety Notice",
] as const;

function getCategoryClass(category: string) {
  const normalized = category.toLowerCase();

  if (normalized.includes("robbery")) return "robbery";
  if (normalized.includes("suspicious")) return "suspicious";
  if (normalized.includes("safety")) return "safety";

  return "default";
}

function buildAlertsGeoJson(alerts: AlertMarker[]): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features: alerts.map((alert) => ({
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

  const [selectedCategories, setSelectedCategories] = useState<string[]>([
    ...ALERT_CATEGORIES,
  ]);

  const filteredAlerts = useMemo(() => {
    return mockAlerts.filter((alert) =>
      selectedCategories.includes(alert.category)
    );
  }, [selectedCategories]);

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
        data: buildAlertsGeoJson(mockAlerts),
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

        if (cluster.geometry.type !== "Point") return;

        map.easeTo({
          center: cluster.geometry.coordinates as [number, number],
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

  useEffect(() => {
    const map = mapRef.current;

    if (!map) return;

    const source = map.getSource("alerts") as GeoJSONSource | undefined;

    if (!source) return;

    popupRef.current?.remove();
    popupRef.current = null;

    source.setData(buildAlertsGeoJson(filteredAlerts));
  }, [filteredAlerts]);

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
        <div class="popup-content">
          <strong>${title}</strong>
          <span>${category}</span>
          <span>${address}</span>
          <small>${reportedAt}</small>
        </div>
      `)
      .addTo(map);
  }

  function zoomToAlert(alertId: number) {
    const alert = filteredAlerts.find((item) => item.id === alertId);
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

  function toggleCategory(category: string) {
    setSelectedCategories((current) => {
      if (current.includes(category)) {
        return current.filter((item) => item !== category);
      }

      return [...current, category];
    });
  }

  return (
    <div className="map-layout">
      <aside className="alert-sidebar">
        <h2>Mock Alerts</h2>

        <div className="map-legend">
          {ALERT_CATEGORIES.map((category) => (
            <label key={category} className="category-filter">
              <input
                type="checkbox"
                checked={selectedCategories.includes(category)}
                onChange={() => toggleCategory(category)}
              />
              <span
                className={`legend-dot category-${getCategoryClass(category)}`}
              />
              {category}
            </label>
          ))}
        </div>

        <div className="alert-list">
          {filteredAlerts.map((alert) => (
            <button
              key={alert.id}
              className="alert-card"
              onClick={() => zoomToAlert(alert.id)}
            >
              <strong>{alert.title}</strong>
              <span
                className={`alert-category category-${getCategoryClass(
                  alert.category
                )}`}
              >
                {alert.category}
              </span>
              <small>{alert.address}</small>
            </button>
          ))}

          {filteredAlerts.length === 0 && (
            <p className="empty-state">No alerts match the selected filters.</p>
          )}
        </div>
      </aside>

      <div ref={mapContainer} className="map-container" />
    </div>
  );
}