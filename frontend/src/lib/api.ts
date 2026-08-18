import type { AlertMarker } from "./mockAlerts";

type AlertsApiResponse = {
  alerts: AlertMarker[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function fetchAlerts(
  recentHours?: number
): Promise<AlertMarker[]> {
  const url = new URL(`${API_BASE_URL}/api/alerts`);

  if (recentHours !== undefined) {
    url.searchParams.set("hours", String(recentHours));
  }

  const response = await fetch(url.toString(), {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch alerts: ${response.status}`
    );
  }

  const data: AlertsApiResponse = await response.json();

  return data.alerts;
}