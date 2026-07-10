"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { AlertMarker } from "../lib/mockAlerts";
import { getAlertCategoryCounts } from "../lib/alertStats";
import { CATEGORY_COLORS, getCategoryClass } from "../lib/categories";

type CategoryChartProps = {
  alerts: AlertMarker[];
};

export default function CategoryChart({ alerts }: CategoryChartProps) {
  const data = getAlertCategoryCounts(alerts);

  if (data.length === 0) {
    return (
      <section className="category-chart">
        <h3>Alerts by Category</h3>
        <p className="empty-state">No chart data available.</p>
      </section>
    );
  }

  return (
    <section className="category-chart">
      <h3>Alerts by Category</h3>

      <div className="category-chart-container">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} layout="vertical" margin={{ left: 12 }}>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="category"
              width={120}
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              cursor={{ fill: "rgba(255, 255, 255, 0.08)" }}
              formatter={(value) => [value, "Alerts"]}
            />
            <Bar dataKey="count" radius={[0, 6, 6, 0]}>
              {data.map((entry) => {
                const categoryClass = getCategoryClass(entry.category);
                const color =
                  CATEGORY_COLORS[
                    categoryClass as keyof typeof CATEGORY_COLORS
                  ] ?? CATEGORY_COLORS.default;

                return <Cell key={entry.category} fill={color} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}