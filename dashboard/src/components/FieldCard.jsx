import React from "react";

// Same thresholds as the backend's rule-based scheduler, kept in sync by
// eye for now. If the scheduler's thresholds change, update these too.
const DRY_THRESHOLD = 25;
const WET_THRESHOLD = 60;

function statusFor(moisture) {
  if (moisture === null || moisture === undefined) {
    return { label: "No data yet", tone: "muted" };
  }
  if (moisture <= DRY_THRESHOLD) {
    return { label: "Needs water", tone: "critical" };
  }
  if (moisture >= WET_THRESHOLD) {
    return { label: "Wet", tone: "info" };
  }
  return { label: "Healthy", tone: "good" };
}

function minutesAgo(isoString) {
  if (!isoString) return null;
  const diffMs = Date.now() - new Date(isoString).getTime();
  return Math.max(0, Math.round(diffMs / 60000));
}

function freshnessLabel(minutes) {
  if (minutes === null) return "No readings yet";
  if (minutes < 1) return "Updated just now";
  if (minutes === 1) return "Updated 1 minute ago";
  if (minutes < 60) return `Updated ${minutes} minutes ago`;
  return "Updated over an hour ago";
}

export default function FieldCard({ field, reading }) {
  const moisture = reading?.soil_moisture ?? null;
  const status = statusFor(moisture);
  const mins = minutesAgo(reading?.recorded_at);
  const stale = mins !== null && mins > 15;

  return (
    <article className={`field-card tone-${status.tone}`}>
      <header className="field-card__header">
        <h3>{field.name}</h3>
        <span className={`status-dot status-dot--${status.tone}`} aria-hidden="true" />
      </header>

      <div className="field-card__moisture">
        <span className="field-card__moisture-value">
          {moisture !== null ? Math.round(moisture) : "--"}
          {moisture !== null && <span className="field-card__unit">%</span>}
        </span>
        <span className={`field-card__status-label tone-text-${status.tone}`}>
          {stale ? "Node offline" : status.label}
        </span>
      </div>

      <dl className="field-card__meta">
        <div>
          <dt>Temperature</dt>
          <dd>{reading?.temperature !== undefined ? `${reading.temperature}°C` : "--"}</dd>
        </div>
        <div>
          <dt>Humidity</dt>
          <dd>{reading?.humidity !== undefined ? `${reading.humidity}%` : "--"}</dd>
        </div>
      </dl>

      <p className="field-card__freshness">{stale ? "No reading in over 15 minutes" : freshnessLabel(mins)}</p>
    </article>
  );
}
