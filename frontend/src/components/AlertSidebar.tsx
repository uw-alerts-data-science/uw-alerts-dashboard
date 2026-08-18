import type { AlertMarker } from "../lib/mockAlerts";
import { getCategoryClass } from "../lib/categories";

type AlertSidebarProps = {
  alerts: AlertMarker[];
  onAlertClick: (alertId: number) => void;
  isLoading: boolean;
  errorMessage: string | null;
};

export default function AlertSidebar({
  alerts,
  onAlertClick,
  isLoading,
  errorMessage,
}: AlertSidebarProps) {
  return (
    <aside className="alert-sidebar">
      <h2>Recent Alerts</h2>

      {isLoading && (
        <p className="empty-state">
          Loading recent alerts...
        </p>
      )}

      {errorMessage && (
        <p className="error-state">
          {errorMessage}
        </p>
      )}

      {!isLoading &&
        !errorMessage &&
        alerts.length === 0 && (
          <div className="no-active-alerts">
            No active alerts at this time.
          </div>
        )}

      {!isLoading &&
        !errorMessage &&
        alerts.length > 0 && (
          <div className="alert-list">
            {alerts.map((alert) => (
              <button
                key={alert.id}
                type="button"
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
          </div>
        )}
    </aside>
  );
}