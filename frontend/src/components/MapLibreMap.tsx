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
  getCategoryClass,
} from "../lib/categories";

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type MapLibreMapProps = {
  recentHours?: number;
  historicalLayout?: boolean;
};

type HistoricalTimeRange = "all" | "year" | "month";

const HISTORICAL_WEEKDAYS = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
] as const;

type HistoricalWeekday =
  (typeof HISTORICAL_WEEKDAYS)[number];

const weekdayFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "short",
  timeZone: "America/Los_Angeles",
});

const HISTORICAL_CATEGORIES = [
  "All",
  "Robbery",
  "Assault",
  "Suspicious Activity",
  "Suspicious Person",
  "Fire",
  "Medical Emergency",
  "Hazardous Materials",
  "Sexual Assault",
  "Theft",
  "Motor Vehicle Incident",
  "Disturbance",
  "Other",
] as const;

type HistoricalTimelineMode = "monthly" | "yearly";

type HistoricalTimelinePoint = {
  key: string;
  label: string;
  count: number;
};

const FIRST_HISTORICAL_YEAR = 2018;

const pacificYearMonthFormatter = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "2-digit",
  timeZone: "America/Los_Angeles",
});

const monthAxisFormatter = new Intl.DateTimeFormat("en-US", {
  month: "short",
  year: "2-digit",
  timeZone: "UTC",
});


type HistoricalCategory =
  (typeof HISTORICAL_CATEGORIES)[number];

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

  const [alerts, setAlerts] = useState<AlertMarker[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMapLoaded, setIsMapLoaded] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const [historicalCategories, setHistoricalCategories] =
  useState<string[]>([]);

  const [historicalTimelineMode, setHistoricalTimelineMode] =
  useState<HistoricalTimelineMode>("monthly");

  const [historicalTimeRange, setHistoricalTimeRange] =
  useState<HistoricalTimeRange>("all");


  const pacificHourFormatter = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    hourCycle: "h23",
    timeZone: "America/Los_Angeles",
  });

  function formatHourLabel(hour: number) {
    const displayHour = hour % 12 || 12;
    const suffix = hour < 12 ? "AM" : "PM";

    return `${displayHour} ${suffix}`;
  }

  const historicalTimeFilteredAlerts = useMemo(() => {
    if (!historicalLayout || historicalTimeRange === "all") {
      return alerts;
    }

    const now = new Date();
    const cutoffDate = new Date(now);

    if (historicalTimeRange === "year") {
      cutoffDate.setFullYear(cutoffDate.getFullYear() - 1);
    }

    if (historicalTimeRange === "month") {
      cutoffDate.setMonth(cutoffDate.getMonth() - 1);
    }

    return alerts.filter((alert) => {
      if (!alert.reportedAt) {
        return false;
      }

      const reportedDate = new Date(alert.reportedAt);

      if (Number.isNaN(reportedDate.getTime())) {
        return false;
      }

      return reportedDate >= cutoffDate && reportedDate <= now;
    });
  }, [alerts, historicalLayout, historicalTimeRange]);


  const filteredAlerts = useMemo(() => {
    if (historicalLayout) {
      const timeFilteredAlerts =
        historicalTimeRange === "all"
          ? alerts
          : historicalTimeFilteredAlerts;

      if (historicalCategories.length === 0) {
        return timeFilteredAlerts;
      }

      return timeFilteredAlerts.filter((alert) =>
        historicalCategories.includes(alert.category)
      );
    }
    // Live page shows every incident returned by the recent-hours API.
    return alerts;
  }, [
    alerts,
    historicalLayout,
    historicalCategories,
    historicalTimeRange,
    historicalTimeFilteredAlerts,
  ]);




  const historicalStats = useMemo(() => {
  const totalIncidents = filteredAlerts.length;

  if (totalIncidents === 0) {
    return {
      totalIncidents: 0,
      mostCommonType: "No data",
      mostCommonTypeCount: 0,
    };
  }

  const categoryCounts = filteredAlerts.reduce<Record<string, number>>(
      (counts, alert) => {
        counts[alert.category] = (counts[alert.category] ?? 0) + 1;
        return counts;
      },
      {}
    );

    const [mostCommonType, mostCommonTypeCount] = Object.entries(
      categoryCounts
    ).sort(([categoryA, countA], [categoryB, countB]) => {
      if (countA !== countB) {
        return countB - countA;
      }

      return categoryA.localeCompare(categoryB);
    })[0];

    return {
      totalIncidents,
      mostCommonType,
      mostCommonTypeCount,
    };
  }, [filteredAlerts]);

  const historicalCategoryCounts = useMemo(() => {
    const total = filteredAlerts.length;

    if (total === 0) {
      return [];
    }

    const counts = filteredAlerts.reduce<Record<string, number>>(
      (result, alert) => {
        result[alert.category] =
          (result[alert.category] ?? 0) + 1;

        return result;
      },
      {}
    );

    return Object.entries(counts)
      .map(([category, count]) => ({
        category,
        count,
        percentage: Math.round((count / total) * 100),
      }))
      .sort((a, b) => {
        if (a.count !== b.count) {
          return b.count - a.count;
        }

        return a.category.localeCompare(b.category);
      });
  }, [filteredAlerts]);


  const historicalWeekdayStats = useMemo(() => {
    const counts: Record<HistoricalWeekday, number> = {
      Mon: 0,
      Tue: 0,
      Wed: 0,
      Thu: 0,
      Fri: 0,
      Sat: 0,
      Sun: 0,
    };

    let unavailableDateCount = 0;

    for (const alert of filteredAlerts) {
      if (!alert.reportedAt) {
        unavailableDateCount += 1;
        continue;
      }

      const reportedDate = new Date(alert.reportedAt);

      if (Number.isNaN(reportedDate.getTime())) {
        unavailableDateCount += 1;
        continue;
      }

      const weekday = weekdayFormatter.format(
        reportedDate
      ) as HistoricalWeekday;

      if (weekday in counts) {
        counts[weekday] += 1;
      } else {
        unavailableDateCount += 1;
      }
    }

    const days = HISTORICAL_WEEKDAYS.map((day) => ({
      day,
      count: counts[day],
    }));

    const maxCount = Math.max(
      1,
      ...days.map((item) => item.count)
    );

    const totalWithDates = days.reduce(
      (total, item) => total + item.count,
      0
    );

    return {
      days,
      maxCount,
      totalWithDates,
      unavailableDateCount,
    };
  }, [filteredAlerts]);

  const historicalTwoHourStats = useMemo(() => {
    const bucketCounts = Array.from({ length: 12 }, () => 0);

    let incidentsWithValidTimes = 0;
    let unavailableTimeCount = 0;

    for (const alert of filteredAlerts) {
      if (!alert.reportedAt) {
        unavailableTimeCount += 1;
        continue;
      }

      const reportedDate = new Date(alert.reportedAt);

      if (Number.isNaN(reportedDate.getTime())) {
        unavailableTimeCount += 1;
        continue;
      }

      const hourPart = pacificHourFormatter
        .formatToParts(reportedDate)
        .find((part) => part.type === "hour");

      const hour = Number(hourPart?.value);

      if (!Number.isInteger(hour) || hour < 0 || hour > 23) {
        unavailableTimeCount += 1;
        continue;
      }

      const bucketIndex = Math.floor(hour / 2);

      bucketCounts[bucketIndex] += 1;
      incidentsWithValidTimes += 1;
    }

    const labels = [
      "12–2 AM",
      "2–4 AM",
      "4–6 AM",
      "6–8 AM",
      "8–10 AM",
      "10–12 PM",
      "12–2 PM",
      "2–4 PM",
      "4–6 PM",
      "6–8 PM",
      "8–10 PM",
      "10–12 AM",
    ];

    const maxCount = Math.max(1, ...bucketCounts);

    let peakIndex: number | null = null;
    let peakCount = 0;

    if (incidentsWithValidTimes > 0) {
      peakIndex = 0;
      peakCount = bucketCounts[0];

      for (let index = 1; index < bucketCounts.length; index += 1) {
        if (bucketCounts[index] > peakCount) {
          peakIndex = index;
          peakCount = bucketCounts[index];
        }
      }
    }

    return {
      buckets: bucketCounts.map((count, index) => ({
        index,
        count,
        label: labels[index],
        percentageOfPeak: count / maxCount,
      })),
      maxCount,
      peakIndex,
      peakCount,
      peakLabel:
        peakIndex === null ? "No data" : labels[peakIndex],
      totalWithValidTimes: incidentsWithValidTimes,
      unavailableTimeCount,
    };
  }, [filteredAlerts]);




  const historicalTimelineData = useMemo<HistoricalTimelinePoint[]>(() => {
    const nowParts = pacificYearMonthFormatter.formatToParts(new Date());

    const currentYear = Number(
      nowParts.find((part) => part.type === "year")?.value
    );

    const currentMonth = Number(
      nowParts.find((part) => part.type === "month")?.value
    );

    if (
      !Number.isInteger(currentYear) ||
      !Number.isInteger(currentMonth)
    ) {
      return [];
    }

    const incidentDateParts = filteredAlerts.flatMap((alert) => {
      if (!alert.reportedAt) {
        return [];
      }

      const date = new Date(alert.reportedAt);

      if (Number.isNaN(date.getTime())) {
        return [];
      }

      const parts = pacificYearMonthFormatter.formatToParts(date);

      const year = Number(
        parts.find((part) => part.type === "year")?.value
      );

      const month = Number(
        parts.find((part) => part.type === "month")?.value
      );

      if (!Number.isInteger(year) || !Number.isInteger(month)) {
        return [];
      }

      return [{ year, month }];
    });

    if (historicalTimelineMode === "yearly") {
      const countsByYear = new Map<number, number>();

      for (
        let year = FIRST_HISTORICAL_YEAR;
        year <= currentYear;
        year += 1
      ) {
        countsByYear.set(year, 0);
      }

      for (const incident of incidentDateParts) {
        if (
          incident.year >= FIRST_HISTORICAL_YEAR &&
          incident.year <= currentYear
        ) {
          countsByYear.set(
            incident.year,
            (countsByYear.get(incident.year) ?? 0) + 1
          );
        }
      }

      return Array.from(countsByYear.entries()).map(([year, count]) => ({
        key: String(year),
        label: String(year),
        count,
      }));
    }

    /*
     * Rolling 12-month view, including the current month.
     */
    const currentMonthIndex =
      currentYear * 12 + (currentMonth - 1);

    const monthlyPoints: HistoricalTimelinePoint[] = [];
    const monthlyCountIndexes = new Map<string, number>();

    for (let offset = -11; offset <= 0; offset += 1) {
      const absoluteMonthIndex = currentMonthIndex + offset;

      const year = Math.floor(absoluteMonthIndex / 12);
      const zeroBasedMonth =
        ((absoluteMonthIndex % 12) + 12) % 12;
      const month = zeroBasedMonth + 1;

      const key = `${year}-${String(month).padStart(2, "0")}`;

      const label = monthAxisFormatter.format(
        new Date(Date.UTC(year, zeroBasedMonth, 1))
      );

      monthlyCountIndexes.set(key, monthlyPoints.length);

      monthlyPoints.push({
        key,
        label,
        count: 0,
      });
    }

    for (const incident of incidentDateParts) {
      const key = `${incident.year}-${String(incident.month).padStart(
        2,
        "0"
      )}`;

      const pointIndex = monthlyCountIndexes.get(key);

      if (pointIndex === undefined) {
        continue;
      }

      monthlyPoints[pointIndex] = {
        ...monthlyPoints[pointIndex],
        count: monthlyPoints[pointIndex].count + 1,
      };
    }

    return monthlyPoints;
  }, [filteredAlerts, historicalTimelineMode]);

  const historicalTimelineTotal = useMemo(() => {
    return historicalTimelineData.reduce(
      (total, point) => total + point.count,
      0
    );
  }, [historicalTimelineData]);





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



  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style:
        "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
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



  function toggleHistoricalCategory(category: string) {
    if (category === "All") {
      setHistoricalCategories([]);
      return;
    }

    setHistoricalCategories((current) => {
      if (current.includes(category)) {
        return current.filter((item) => item !== category);
      }

      return [...current, category];
    });
  }


  if (historicalLayout) {
    return (
      <main className="historical-dashboard">
        <header className="historical-dashboard-header">
          <div>
            <h1>Incident Analytics</h1>
            {/* <p>
              Aggregated, de-identified trends from published
              alerts
            </p> */}
          </div>

          <label className="historical-period-control">
            <span className="historical-visually-hidden">
              Historical time range
            </span>

            <select
              value={historicalTimeRange}
              onChange={(event) =>
                setHistoricalTimeRange(
                  event.target.value as HistoricalTimeRange
                )
              }
            >
              <option value="all">All Time</option>
              <option value="year">Last Year</option>
              <option value="month">Last Month</option>
            </select>
          </label>
        </header>

        <section className="historical-filter-bar">
          <span className="historical-filter-label">
            Filters
          </span>

          {HISTORICAL_CATEGORIES.map((category) => {
            const isAll = category === "All";
          
            const isActive = isAll
              ? historicalCategories.length === 0
              : historicalCategories.includes(category);
          
            return (
              <button
                key={category}
                type="button"
                className={`historical-filter-chip ${
                  isActive ? "active" : ""
                }`}
                aria-pressed={isActive}
                onClick={() => toggleHistoricalCategory(category)}
              >
                {category}
              </button>
            );
          })}
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
                    : historicalCategories.length === 0
                      ? `${filteredAlerts.length} mapped incidents`
                      : `${filteredAlerts.length} incidents across ${
                          historicalCategories.length
                        } selected ${
                          historicalCategories.length === 1
                            ? "category"
                            : "categories"
                        }`}
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
                                    
                <strong className="historical-summary-value">
                  {isLoading ? "—" : historicalStats.totalIncidents}
                </strong>
                                    
                <span className="historical-summary-description">
                  {historicalCategories.length === 0
                    ? "Across all categories"
                    : `Across ${historicalCategories.length} selected ${
                        historicalCategories.length === 1
                          ? "category"
                          : "categories"
                      }`}
                </span>
              </article>
                    
              <article className="historical-summary-card">
                <h2>Most Common Type</h2>
                    
                <strong className="historical-summary-value historical-summary-category">
                  {isLoading ? "—" : historicalStats.mostCommonType}
                </strong>
                    
                <span className="historical-summary-description">
                  {historicalStats.mostCommonTypeCount > 0
                    ? `${historicalStats.mostCommonTypeCount} ${
                        historicalStats.mostCommonTypeCount === 1
                          ? "incident"
                          : "incidents"
                      }`
                    : "No incidents available"}
                </span>
              </article>

              <article className="historical-summary-card historical-hourly-card">
                <div className="historical-hourly-heading">
                  <h2>Activity by Time of Day</h2>
                  <span>Pacific Time</span>
                </div>

                {isLoading ? (
                  <p className="historical-chart-empty">
                    Loading incident data...
                  </p>
                ) : historicalTwoHourStats.totalWithValidTimes === 0 ? (
                  <p className="historical-chart-empty">
                    No valid incident times available.
                  </p>
                ) : (
                  <div className="historical-hourly-content">
                    <svg
                      className="historical-hourly-radial"
                      viewBox="0 0 240 240"
                      role="img"
                      aria-label="Incidents by two-hour period of day"
                    >
                      {historicalTwoHourStats.buckets.map((item) => {
                        /*
                         * Each two-hour period occupies 30 degrees.
                         * Leaving about 3 degrees empty creates a small gap
                         * between neighboring wedges.
                         */
                        const sectionAngle = 360 / 12;
                        const gap = 3;
                      
                        const startAngle =
                          item.index * sectionAngle -
                          90 +
                          gap / 2;
                      
                        const endAngle =
                          (item.index + 1) * sectionAngle -
                          90 -
                          gap / 2;
                      
                        const innerRadius = 43;
                      
                        /*
                         * Even periods with no incidents retain a very short
                         * wedge so all 12 time periods remain visible.
                         */
                        const minimumOuterRadius = 53;
                        const maximumOuterRadius = 94;
                      
                        const outerRadius =
                          item.count === 0
                            ? minimumOuterRadius
                            : minimumOuterRadius +
                              item.percentageOfPeak *
                                (maximumOuterRadius - minimumOuterRadius);
                      
                        const centerX = 120;
                        const centerY = 120;
                      
                        const toRadians = (degrees: number) =>
                          (degrees * Math.PI) / 180;
                      
                        const pointAt = (
                          radius: number,
                          angle: number
                        ) => ({
                          x:
                            centerX +
                            radius * Math.cos(toRadians(angle)),
                          y:
                            centerY +
                            radius * Math.sin(toRadians(angle)),
                        });
                      
                        const innerStart = pointAt(
                          innerRadius,
                          startAngle
                        );
                      
                        const innerEnd = pointAt(
                          innerRadius,
                          endAngle
                        );
                      
                        const outerStart = pointAt(
                          outerRadius,
                          startAngle
                        );
                      
                        const outerEnd = pointAt(
                          outerRadius,
                          endAngle
                        );
                      
                        const path = [
                          `M ${innerStart.x} ${innerStart.y}`,
                          `L ${outerStart.x} ${outerStart.y}`,
                          `A ${outerRadius} ${outerRadius} 0 0 1 ${outerEnd.x} ${outerEnd.y}`,
                          `L ${innerEnd.x} ${innerEnd.y}`,
                          `A ${innerRadius} ${innerRadius} 0 0 0 ${innerStart.x} ${innerStart.y}`,
                          "Z",
                        ].join(" ");
                      
                        const isPeak =
                          item.index ===
                          historicalTwoHourStats.peakIndex;
                      
                        return (
                          <path
                            key={item.index}
                            d={path}
                            className={
                              isPeak
                                ? "historical-hourly-wedge historical-hourly-wedge-peak"
                                : "historical-hourly-wedge"
                            }
                            style={{
                              opacity:
                                item.count === 0
                                  ? 0.14
                                  : 0.4 +
                                    item.percentageOfPeak * 0.6,
                            }}
                          >
                            <title>
                              {item.label}: {item.count}{" "}
                              {item.count === 1
                                ? "incident"
                                : "incidents"}
                            </title>
                          </path>
                        );
                      })}

                      {/* Time labels around the outside */}
                      {historicalTwoHourStats.buckets.map((item) => {
                        const angle =
                          ((item.index + 0.5) / 12) *
                            Math.PI *
                            2 -
                          Math.PI / 2;
                      
                        const labelRadius = 110;
                      
                        const x =
                          120 + Math.cos(angle) * labelRadius;
                      
                        const y =
                          120 + Math.sin(angle) * labelRadius;
                      
                        return (
                          <text
                            key={`label-${item.index}`}
                            x={x}
                            y={y}
                            className="historical-hourly-label"
                            textAnchor="middle"
                            dominantBaseline="middle"
                          >
                            {item.label}
                          </text>
                        );
                      })}

                      {/* Inner circle */}
                      <circle
                        cx="120"
                        cy="120"
                        r="38"
                        className="historical-hourly-center"
                      />

                      <text
                        x="120"
                        y="116"
                        className="historical-hourly-peak-value"
                        textAnchor="middle"
                        dominantBaseline="middle"
                      >
                        {historicalTwoHourStats.peakLabel}
                      </text>
                    
                      <text
                        x="120"
                        y="132"
                        className="historical-hourly-peak-label"
                        textAnchor="middle"
                        dominantBaseline="middle"
                      >
                        PEAK
                      </text>
                    </svg>
                    
                    <span className="historical-hourly-summary">
                      {historicalTwoHourStats.peakCount}{" "}
                      {historicalTwoHourStats.peakCount === 1
                        ? "incident"
                        : "incidents"}{" "}
                      during the busiest two-hour period
                    </span>
                  </div>
                )}
              </article>
            </div>

            <article className="historical-panel historical-wide-chart">
              <div className="historical-chart-heading">
                <div>
                  <h2>Incidents Over Time</h2>

                  <span>
                    {historicalTimelineMode === "monthly"
                      ? `${historicalTimelineTotal} incidents over the last 12 months`
                      : `${historicalTimelineTotal} incidents since ${FIRST_HISTORICAL_YEAR}`}
                  </span>
                </div>
                    
                <label className="historical-chart-selector">
                  <span className="historical-visually-hidden">
                    Timeline grouping
                  </span>
                    
                  <select
                    value={historicalTimelineMode}
                    onChange={(event) =>
                      setHistoricalTimelineMode(
                        event.target.value as HistoricalTimelineMode
                      )
                    }
                  >
                    <option value="monthly">Last 12 months</option>
                    <option value="yearly">By year</option>
                  </select>
                </label>
              </div>
                  
              {isLoading ? (
                <p className="historical-chart-empty">
                  Loading incident data...
                </p>
              ) : historicalTimelineData.length === 0 ? (
                <p className="historical-chart-empty">
                  No incident timeline data available.
                </p>
              ) : (
                <div className="historical-timeline-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={historicalTimelineData}
                      margin={{
                        top: 12,
                        right: 16,
                        bottom: 4,
                        left: 0,
                      }}
                    >
                      <defs>
                        <linearGradient
                          id="historicalTimelineFill"
                          x1="0"
                          y1="0"
                          x2="0"
                          y2="1"
                        >
                          <stop
                            offset="0%"
                            stopColor="#8f6bc7"
                            stopOpacity={0.22}
                          />

                          <stop
                            offset="100%"
                            stopColor="#8f6bc7"
                            stopOpacity={0.02}
                          />
                        </linearGradient>
                      </defs>
                    
                      <CartesianGrid
                        vertical={false}
                        stroke="#2a2235"
                        strokeDasharray="3 3"
                      />

                      <XAxis
                        dataKey="label"
                        axisLine={false}
                        tickLine={false}
                        interval={0}
                        minTickGap={8}
                        tick={{
                          fill: "#85779e",
                          fontSize:
                            historicalTimelineMode === "yearly" ? 11 : 10,
                        }}
                      />

                      <YAxis
                        allowDecimals={false}
                        axisLine={false}
                        tickLine={false}
                        width={32}
                        tick={{
                          fill: "#85779e",
                          fontSize: 10,
                        }}
                      />

                      <Tooltip
                        cursor={{
                          stroke: "#6f5a87",
                          strokeDasharray: "4 4",
                        }}
                        contentStyle={{
                          border: "1px solid #3a2c49",
                          borderRadius: "8px",
                          background: "#17101f",
                          color: "#f5efff",
                          fontSize: "12px",
                        }}
                        formatter={(value) => [
                          `${Number(value)} ${
                            Number(value) === 1 ? "incident" : "incidents"
                          }`,
                          "Total",
                        ]}
                      />

                      <Area
                        type="linear"
                        dataKey="count"
                        stroke="none"
                        fill="url(#historicalTimelineFill)"
                        isAnimationActive
                      />

                      <Line
                        type="linear"
                        dataKey="count"
                        stroke="#9a72d8"
                        strokeWidth={2.5}
                        dot={{
                          r: 3,
                          fill: "#e0ad57",
                          stroke: "#17101f",
                          strokeWidth: 2,
                        }}
                        activeDot={{
                          r: 5,
                          fill: "#e0ad57",
                          stroke: "#17101f",
                          strokeWidth: 2,
                        }}
                        isAnimationActive
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </article>

            <div className="historical-bottom-grid">
              <article className="historical-panel historical-chart-card">
                <h2>Incidents by Type</h2>

                {isLoading ? (
                  <p className="historical-chart-empty">
                    Loading incident data...
                  </p>
                ) : historicalCategoryCounts.length === 0 ? (
                  <p className="historical-chart-empty">
                    No incident data available.
                  </p>
                ) : (
                  <div className="historical-type-list">
                    {historicalCategoryCounts.map((item) => {
                      const categoryClass = getCategoryClass(item.category);
                    
                      const barColor =
                        CATEGORY_COLORS[
                          categoryClass as keyof typeof CATEGORY_COLORS
                        ] ?? CATEGORY_COLORS.other;
                      
                      return (
                        <div
                          key={item.category}
                          className="historical-type-row"
                        >
                          <div className="historical-type-header">
                            <span className="historical-type-name">
                              {item.category}
                            </span>
                      
                            <span className="historical-type-count">
                              {item.count}
                            </span>
                      
                            <span className="historical-type-percentage">
                              {item.percentage}%
                            </span>
                          </div>
                      
                          <div className="historical-type-track">
                            <div
                              className="historical-type-bar"
                              style={{
                                width: `${item.percentage}%`,
                                backgroundColor: barColor,
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </article>
              <article className="historical-panel historical-chart-card">
                <h2>Incidents by Day of Week</h2>

                {isLoading ? (
                  <p className="historical-chart-empty">
                    Loading incident data...
                  </p>
                ) : historicalWeekdayStats.totalWithDates === 0 ? (
                  <p className="historical-chart-empty">
                    No incidents with valid date information.
                  </p>
                ) : (
                  <>
                    <div className="historical-weekday-chart">
                      {historicalWeekdayStats.days.map((item) => {
                        const heightPercentage =
                          item.count === 0
                            ? 0
                            : Math.max(
                                8,
                                (item.count /
                                  historicalWeekdayStats.maxCount) *
                                  100
                              );
                            
                        return (
                          <div
                            key={item.day}
                            className="historical-weekday-column"
                          >
                            <span className="historical-weekday-count">
                              {item.count}
                            </span>
                        
                            <div className="historical-weekday-track">
                              <div
                                className="historical-weekday-bar"
                                style={{
                                  height: `${heightPercentage}%`,
                                }}
                              />
                            </div>
                              
                            <span className="historical-weekday-label">
                              {item.day}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    
                    <p className="historical-weekday-note">
                      Incident counts by reported weekday in Pacific Time.
                      {historicalWeekdayStats.unavailableDateCount > 0 &&
                        ` ${historicalWeekdayStats.unavailableDateCount} incident${
                          historicalWeekdayStats.unavailableDateCount === 1
                            ? " was"
                            : "s were"
                        } excluded because no valid date was available.`}
                    </p>
                  </>
                )}
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
        Alerts
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