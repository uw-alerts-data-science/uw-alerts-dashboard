import type { FeatureCollection, Point } from "geojson";
import type { AlertMarker } from "./mockAlerts";
import { getCategoryClass } from "./categories";

export function buildAlertsGeoJson(
  alerts: AlertMarker[]
): FeatureCollection<Point> {
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