"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, {
  GeoJSONSource,
  MapMouseEvent,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import AlertSidebar from "./AlertSidebar";
import type { AlertMarker } from "../lib/mockAlerts";
import { fetchAlerts } from "../lib/api";
import { buildAlertsGeoJson } from "../lib/alertMapData";
import {
  CATEGORY_COLORS,
  getAlertCategories,
} from "../lib/categories";

type MapLibreMapProps = {
  recentHours?: number;
  historicalLayout?: boolean;
};

type PopupDetails = {
  coordinates: [number, number];
  title: string;
  category: string;
  address: string;
  reportedAt: string;
};

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export default function MapLibreMap({
  recentHours,
  historicalLayout = false,
}: MapLibreMapProps) {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const hasInitializedFilters = useRef(false);

  const [alerts, setAlerts] = useState<AlertMarker[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const categories = useMemo(() => {
    return getAlertCategories(alerts);
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) =>
      selectedCategories.includes(alert.category)
    );
  }, [alerts, selectedCategories]);

  /*
   * Load alerts from FastAPI.
   *
   * With recentHours:
   *   /api/alerts?hours=6
   *
   * Without recentHours:
   *   /api/alerts
   */
  useEffect(() => {
    let cancelled = false;

    async function loadAlerts() {
      try {
        setIsLoading(true);
        setErrorMessage(null);

        const apiAlerts = await fetchAlerts(recentHours);

        if (!cancelled) {
          setAlerts(apiAlerts);
        }
      } catch (error) {
        console.error("Failed to load alerts:", error);

        if (!cancelled) {
          setErrorMessage("Unable to load alerts.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadAlerts();

    return () => {
      cancelled = true;
    };
  }, [recentHours]);

  /*
   * Select every category after the API data first loads.
   */
  useEffect(() => {
    if (hasInitializedFilters.current) {
      return;
    }

    if (categories.length === 0) {
      return;
    }

    setSelectedCategories(categories);
    hasInitializedFilters.current = true;
  }, [categories]);

  /*
   * Initialize MapLibre.
   */
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style:
        "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
      center: [-122.3035, 47.6553],
      zoom: historicalLayout ? 11.5 : 12,
    });

    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl(),
      "top-right"
    );

    map.on("load", () => {
      map.addSource("alerts", {
        type: "geojson",
        data: buildAlertsGeoJson([]),
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
          "circle-color": CATEGORY_COLORS.cluster,
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
            CATEGORY_COLORS.robbery,

            "assault",
            CATEGORY_COLORS.assault,

            "suspicious",
            CATEGORY_COLORS.suspicious,

            "fire",
            CATEGORY_COLORS.fire,

            "medical",
            CATEGORY_COLORS.medical,

            "hazmat",
            CATEGORY_COLORS.hazmat,

            "sexualAssault",
            CATEGORY_COLORS.sexualAssault,

            "theft",
            CATEGORY_COLORS.theft,

            "motorVehicle",
            CATEGORY_COLORS.motorVehicle,

            "disturbance",
            CATEGORY_COLORS.disturbance,

            CATEGORY_COLORS.other,
          ],
          "circle-radius": 10,
          "circle-stroke-width": 3,
          "circle-stroke-color": "#ffffff",
        },
      });

      map.on(
        "click",
        "alert-clusters",
        async (event: MapMouseEvent) => {
          const features = map.queryRenderedFeatures(
            event.point,
            {
              layers: ["alert-clusters"],
            }
          );

          const cluster = features[0];

          if (!cluster?.properties) {
            return;
          }

          if (cluster.geometry.type !== "Point") {
            return;
          }

          const clusterId = Number(
            cluster.properties.cluster_id
          );

          const source = map.getSource(
            "alerts"
          ) as GeoJSONSource;

          const zoom =
            await source.getClusterExpansionZoom(clusterId);

          map.easeTo({
            center: cluster.geometry.coordinates as [
              number,
              number,
            ],
            zoom,
          });
        }
      );

      map.on(
        "click",
        "alert-unclustered",
        (event: MapMouseEvent) => {
          const features = map.queryRenderedFeatures(
            event.point,
            {
              layers: ["alert-unclustered"],
            }
          );

          const feature = features[0];

          if (!feature || feature.geometry.type !== "Point") {
            return;
          }

          const properties = feature.properties;

          if (!properties) {
            return;
          }

          openAlertPopup({
            coordinates: feature.geometry.coordinates as [
              number,
              number,
            ],
            title: String(properties.title),
            category: String(properties.category),
            address: String(properties.address),
            reportedAt: String(properties.reportedAt),
          });
        }
      );

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
      setIsMapLoaded(true);
    });

    return () => {
      popupRef.current?.remove();
      popupRef.current = null;

      map.remove();
      mapRef.current = null;

      setIsMapLoaded(false);
    };
  }, [historicalLayout]);

  /*
   * MapLibre needs to be notified whenever its containing card changes size.
   * This is especially important for the smaller historical map container.
   */
  useEffect(() => {
    const container = mapContainer.current;

    if (!container) {
      return;
    }

    const resizeObserver = new ResizeObserver(() => {
      mapRef.current?.resize();
    });

    resizeObserver.observe(container);

    const initialResize = window.setTimeout(() => {
      mapRef.current?.resize();
    }, 100);

    return () => {
      resizeObserver.disconnect();
      window.clearTimeout(initialResize);
    };
  }, [historicalLayout]);

  /*
   * Update the GeoJSON source when alerts or filters change.
   */
  useEffect(() => {
    const map = mapRef.current;

    if (!map || !isMapLoaded) {
      return;
    }

    const source = map.getSource(
      "alerts"
    ) as GeoJSONSource | undefined;

    if (!source) {
      return;
    }

    popupRef.current?.remove();
    popupRef.current = null;

    source.setData(buildAlertsGeoJson(filteredAlerts));
  }, [filteredAlerts, isMapLoaded]);

  function openAlertPopup({
    coordinates,
    title,
    category,
    address,
    reportedAt,
  }: PopupDetails) {
    const map = mapRef.current;

    if (!map) {
      return;
    }

    popupRef.current?.remove();

    popupRef.current = new maplibregl.Popup({
      offset: 18,
    })
      .setLngLat(coordinates)
      .setHTML(`
        <div class="popup-content">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(category)}</span>
          <span>${escapeHtml(address)}</span>
          <small>${escapeHtml(reportedAt)}</small>
        </div>
      `)
      .addTo(map);
  }

  function zoomToAlert(alertId: number) {
    const alert = filteredAlerts.find(
      (item) => item.id === alertId
    );

    const map = mapRef.current;

    if (!alert || !map) {
      return;
    }

    const coordinates: [number, number] = [
      alert.longitude,
      alert.latitude,
    ];

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
        return current.filter(
          (item) => item !== category
        );
      }

      return [...current, category];
    });
  }

  /*
   * Historical analytics layout.
   *
   * This is used only when the historical page passes:
   * <MapLibreMap historicalLayout />
   */
  if (historicalLayout) {
    return (
      <main className="historical-dashboard">
        <header className="historical-dashboard-header">
          <div>
            <h1>Incident Analytics</h1>
            <p>
              Aggregated, de-identified trends from published
              alerts
            </p>
          </div>

          <button
            type="button"
            className="historical-period-button"
          >
            This year
            <span aria-hidden="true">⌄</span>
          </button>
        </header>

        <section className="historical-filter-bar">
          <span className="historical-filter-label">
            Filters
          </span>

          <button
            type="button"
            className="historical-filter-chip active"
          >
            Last 90 days
          </button>

          <button
            type="button"
            className="historical-filter-chip"
          >
            Robbery
          </button>

          <button
            type="button"
            className="historical-filter-chip"
          >
            Assault
          </button>

          <button
            type="button"
            className="historical-filter-chip"
          >
            Theft
          </button>

          <button
            type="button"
            className="historical-filter-chip"
          >
            Suspicious
          </button>
        </section>

        {errorMessage && (
          <p className="historical-error-message">
            {errorMessage}
          </p>
        )}

        <div className="historical-dashboard-grid">
          <section className="historical-panel historical-map-panel">
            <div className="historical-panel-heading">
              <div>
                <h2>Incident Map</h2>
                <span>
                  {isLoading
                    ? "Loading incident locations..."
                    : `${filteredAlerts.length} mapped incidents`}
                </span>
              </div>
            </div>

            <div
              ref={mapContainer}
              className="historical-map-container"
            />
          </section>

          <section className="historical-analytics-content">
            <div className="historical-summary-grid">
              <article className="historical-summary-card">
                <h2>Total Incidents</h2>
              </article>

              <article className="historical-summary-card">
                <h2>Most Common Type</h2>
              </article>

              <article className="historical-summary-card">
                <h2>Most Common Area</h2>
              </article>

              <article className="historical-summary-card">
                <h2>Peak Hour</h2>
              </article>
            </div>

            <article className="historical-panel historical-wide-chart">
              <h2>Incidents Over Time</h2>
            </article>

            <div className="historical-bottom-grid">
              <article className="historical-panel historical-chart-card">
                <h2>Incidents by Type</h2>
              </article>

              <article className="historical-panel historical-chart-card">
                <h2>Incidents by Day of Week</h2>
              </article>
            </div>
          </section>
        </div>
      </main>
    );
  }

  /*
   * Existing Recent Alerts layout.
   */
  return (
    <div className="map-layout">
      <button
        type="button"
        className="mobile-sidebar-toggle"
        onClick={() => setIsSidebarOpen(true)}
        aria-expanded={isSidebarOpen}
        aria-controls="alert-sidebar-panel"
      >
        Alerts & Filters
      </button>

      {isSidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Close alert sidebar"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <div
        id="alert-sidebar-panel"
        className={`sidebar-panel ${
          isSidebarOpen ? "sidebar-panel-open" : ""
        }`}
      >
        <button
          type="button"
          className="mobile-sidebar-close"
          aria-label="Close alert sidebar"
          onClick={() => setIsSidebarOpen(false)}
        >
          ×
        </button>

        <AlertSidebar
          alerts={filteredAlerts}
          categories={categories}
          selectedCategories={selectedCategories}
          onToggleCategory={toggleCategory}
          onAlertClick={(alertId) => {
            zoomToAlert(alertId);
            setIsSidebarOpen(false);
          }}
          isLoading={isLoading}
          errorMessage={errorMessage}
        />
      </div>

      <div
        ref={mapContainer}
        className="map-container"
      />
    </div>
  );
}