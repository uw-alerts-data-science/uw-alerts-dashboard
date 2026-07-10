import type { AlertMarker } from "../lib/mockAlerts";
import { ALERT_CATEGORIES, getCategoryClass } from "../lib/categories";

type AlertSidebarProps = {
  alerts: AlertMarker[];
  selectedCategories: string[];
  onToggleCategory: (category: string) => void;
  onAlertClick: (alertId: number) => void;
};

export default function AlertSidebar({
  alerts,
  selectedCategories,
  onToggleCategory,
  onAlertClick,
}: AlertSidebarProps) {
  return (
    <aside className="alert-sidebar">
      <h2>Mock Alerts</h2>

      <div className="map-legend">
        {ALERT_CATEGORIES.map((category) => (
          <label key={category} className="category-filter">
            <input
              type="checkbox"
              checked={selectedCategories.includes(category)}
              onChange={() => onToggleCategory(category)}
            />
            <span className={`legend-dot category-${getCategoryClass(category)}`} />
            {category}
          </label>
        ))}
      </div>

      <div className="alert-list">
        {alerts.map((alert) => (
          <button
            key={alert.id}
            className="alert-card"
            onClick={() => onAlertClick(alert.id)}
          >
            <strong>{alert.title}</strong>
            <span className={`alert-category category-${getCategoryClass(alert.category)}`}>
              {alert.category}
            </span>
            <small>{alert.address}</small>
          </button>
        ))}

        {alerts.length === 0 && (
          <p className="empty-state">No alerts match the selected filters.</p>
        )}
      </div>
    </aside>
  );
}