import React from "react";

function timeLabel(isoString) {
  return new Date(isoString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function IrrigationLog({ events }) {
  return (
    <section className="panel">
      <h2>Irrigation log</h2>
      {events.length === 0 ? (
        <p className="panel__empty">No irrigation has run yet. It starts once a field drops below the dry threshold.</p>
      ) : (
        <ul className="panel__list">
          {events.map((event) => (
            <li key={event.id} className="log-row">
              <span className="log-row__field">{event.field_name}</span>
              <span className="log-row__detail">
                Opened for {event.duration_min} minutes ({event.source})
              </span>
              <span className="log-row__time">{timeLabel(event.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
