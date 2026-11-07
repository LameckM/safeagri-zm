import React from "react";

export default function StatusPill({ offlineCount, alertCount, awaitingCount = 0 }) {
  if (offlineCount > 0) {
    return (
      <span className="status-pill status-pill--critical">
        {offlineCount} {offlineCount === 1 ? "node" : "nodes"} offline
      </span>
    );
  }
  if (alertCount > 0) {
    return (
      <span className="status-pill status-pill--warning">
        {alertCount} active {alertCount === 1 ? "alert" : "alerts"}
      </span>
    );
  }
  if (awaitingCount > 0) return <span className="status-pill status-pill--warning">{awaitingCount} awaiting readings</span>;
  return <span className="status-pill status-pill--good">All nodes reporting</span>;
}
