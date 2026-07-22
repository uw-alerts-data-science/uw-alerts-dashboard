import CategoryChart from "./CategoryChart";
import type { AlertMarker } from "../lib/mockAlerts";
import { getCategoryClass } from "../lib/categories";

type AlertSidebarProps = {
  alerts: AlertMarker[];
  categories: string[];
  selectedCategories: string[];
  onToggleCategory: (category: string) => void;
  onAlertClick: (alertId: number) => void;
  isLoading: boolean;
  errorMessage: string | null;
};

export default function AlertSidebar({
  alerts,
  categories,
  selectedCategories,
  onToggleCategory,
  onAlertClick,
  isLoading,
  errorMessage,
}: AlertSidebarProps) {
  return (
    <aside className="alert-sidebar">
      <h2>Alerts</h2>
  
      {isLoading && (
        <p className="empty-state">Loading alerts...</p>
      )}
  
      {errorMessage && (
        <p className="error-state">{errorMessage}</p>
      )}
  
      {!isLoading && !errorMessage && categories.length === 0 && (
        <div className="no-active-alerts">
          No active alerts at this time.
        </div>
      )}
  
      {!isLoading && !errorMessage && categories.length > 0 && (
        <>
          <div className="map-legend">
            {categories.map((category) => (
              <label key={category} className="category-filter">
                <input
                  type="checkbox"
                  checked={selectedCategories.includes(category)}
                  onChange={() => onToggleCategory(category)}
                />
  
                <span
                  className={`legend-dot category-${getCategoryClass(
                    category
                  )}`}
                />
  
                {category}
              </label>
            ))}
          </div>
          
          <CategoryChart alerts={alerts} />
          
          <div className="alert-list">
            {alerts.map((alert) => (
              <button
                key={alert.id}
                className="alert-card"
                onClick={() => onAlertClick(alert.id)}
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
  
            {alerts.length === 0 && (
              <p className="empty-state">
                No alerts match the selected filters.
              </p>
            )}
          </div>
        </>
      )}
    </aside>
  );
}