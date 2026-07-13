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

function formatCategoryLabel(category: string) {
  const labelMap: Record<string, string> = {
    "Suspicious Activity": "Suspicious",
    "Suspicious Person": "Suspicious Person",
    "Medical Emergency": "Medical",
    "Hazardous Materials": "Hazmat",
    "Motor Vehicle Incident": "Motor Vehicle",
    "Sexual Assault": "Sexual Assault",
  };

  return labelMap[category] ?? category;
}

export default function CategoryChart({ alerts }: CategoryChartProps) {
  const data = getAlertCategoryCounts(alerts);
  const chartHeight = Math.max(260, data.length * 34);

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
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 12, bottom: 4, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />

            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 12 }}
            />

            <YAxis
              type="category"
              dataKey="category"
              width={110}
              interval={0}
              tick={{ fontSize: 11 }}
              tickFormatter={formatCategoryLabel}
            />

            <Tooltip
              cursor={{ fill: "rgba(255, 255, 255, 0.08)" }}
              formatter={(value) => [value, "Alerts"]}
              labelFormatter={(label) => String(label)}
            />

            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
              {data.map((entry) => {
                const categoryClass = getCategoryClass(entry.category);
                const color =
                  CATEGORY_COLORS[
                    categoryClass as keyof typeof CATEGORY_COLORS
                  ] ?? CATEGORY_COLORS.other;

                return <Cell key={entry.category} fill={color} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}