import type { AlertMarker } from "./mockAlerts";
import { getAlertCategories } from "./categories";

export type CategoryCount = {
  category: string;
  count: number;
};

export function getAlertCategoryCounts(alerts: AlertMarker[]): CategoryCount[] {
  const categories = getAlertCategories(alerts);

  return categories
    .map((category) => ({
      category,
      count: alerts.filter((alert) => alert.category === category).length,
    }))
    .filter((item) => item.count > 0);
}