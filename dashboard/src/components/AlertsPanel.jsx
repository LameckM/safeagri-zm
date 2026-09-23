import React from "react";

function timeLabel(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const KIND_LABEL = {
  sensor_fault: "Sensor fault",
  node_offline: "Node offline",
};

export default function AlertsPanel({ alerts }) {
  return (
    <section className="panel">
      <h2>Alerts</h2>
      {alerts.length === 0 ? (
        <p className="panel__empty">No active alerts. Every sensor is reporting normal values.</p>
      ) : (
        <ul className="panel__list">
          {alerts.map((alert) => (
            <li key={alert.id} className="alert-row">
              <span className={`alert-row__kind alert-row__kind--${alert.kind}`}>
                {KIND_LABEL[alert.kind] || alert.kind}
              </span>
              <span className="alert-row__message">{alert.message}</span>
              <span className="alert-row__time">{timeLabel(alert.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
