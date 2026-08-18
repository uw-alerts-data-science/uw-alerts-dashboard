import type { AlertMarker } from "./mockAlerts";

export const CATEGORY_COLORS = {
  robbery: "#d7263d",
  assault: "#dc2626",
  suspicious: "#f59e0b",
  fire: "#ea580c",
  medical: "#0891b2",
  hazmat: "#84cc16",
  sexualAssault: "#be185d",
  theft: "#9333ea",
  motorVehicle: "#0f766e",
  disturbance: "#64748b",
  other: "#6b7280",
  cluster: "#7c3aed",
} as const;

export function getCategoryClass(category: string) {
  const normalized = category.toLowerCase();

  if (normalized.includes("robbery")) return "robbery";
  if (normalized.includes("assault") && normalized.includes("sexual")) {
    return "sexualAssault";
  }
  if (normalized.includes("assault")) return "assault";
  if (normalized.includes("suspicious")) return "suspicious";
  if (normalized.includes("fire")) return "fire";
  if (normalized.includes("medical")) return "medical";
  if (normalized.includes("hazardous")) return "hazmat";
  if (normalized.includes("theft")) return "theft";
  if (normalized.includes("motor vehicle")) return "motorVehicle";
  if (normalized.includes("disturbance")) return "disturbance";

  return "other";
}

export function getAlertCategories(alerts: AlertMarker[]) {
  const preferredOrder = [
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
  ];

  const categories = Array.from(new Set(alerts.map((alert) => alert.category)));

  return categories.sort((a, b) => {
    const aIndex = preferredOrder.indexOf(a);
    const bIndex = preferredOrder.indexOf(b);

    if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
    if (aIndex === -1) return 1;
    if (bIndex === -1) return -1;

    return aIndex - bIndex;
  });
}