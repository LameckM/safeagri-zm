import React, { useMemo } from "react";

const DAY_MS = 24 * 60 * 60 * 1000;
const formatLiters = (value) => `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} L`;
function dayKey(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function shortDay(key) {
  return new Date(`${key}T12:00:00`).toLocaleDateString([], { weekday: "short", day: "numeric" });
}

export default function WaterUsageChart({ records }) {
  const analysis = useMemo(() => {
    const now = new Date();
    const days = Array.from({ length: 7 }, (_, index) => dayKey(new Date(now.getTime() - (6 - index) * DAY_MS).toISOString()));
    const totalsByDay = Object.fromEntries(days.map((day) => [day, 0]));
    const byField = new Map();
    let total = 0;
    for (const row of records) {
      const liters = Number(row.liters) || 0;
      const day = dayKey(row.recorded_at);
      if (day in totalsByDay) totalsByDay[day] += liters;
      byField.set(row.field_name, (byField.get(row.field_name) || 0) + liters);
      total += liters;
    }
    const fieldTotals = [...byField.entries()].map(([name, liters]) => ({ name, liters })).sort((a, b) => b.liters - a.liters);
    const daily = days.map((day) => ({ day, liters: totalsByDay[day] }));
    return { daily, fieldTotals, total, average: total / 7, activeDays: daily.filter((item) => item.liters > 0).length };
  }, [records]);
  const maxDaily = Math.max(1, ...analysis.daily.map((item) => item.liters));
  const maxField = Math.max(1, ...analysis.fieldTotals.map((item) => item.liters));

  return (
    <section className="panel water-panel">
      <div className="water-panel__heading">
        <div><h2>Water usage analysis</h2><p>Estimated consumption over the last 7 days</p></div>
        <span className="water-panel__unit">Litres (L)</span>
      </div>
      <div className="water-kpis">
        <div><span>Total used</span><strong>{formatLiters(analysis.total)}</strong></div>
        <div><span>Daily average</span><strong>{formatLiters(analysis.average)}</strong></div>
        <div><span>Active usage days</span><strong>{analysis.activeDays} / 7</strong></div>
      </div>
      <div className="water-chart-block">
        <h3>Daily consumption</h3>
        {analysis.total === 0 ? <p className="panel__empty">No water usage recorded yet. Start the simulator to generate usage data.</p> : (
          <div className="water-bars" role="img" aria-label="Bar chart showing daily simulated water consumption in litres">
            {analysis.daily.map((item) => (
              <div className="water-bar-column" key={item.day}>
                <span className="water-bar-value">{item.liters > 0 ? Math.round(item.liters) : "—"}</span>
                <div className="water-bar-track"><div className="water-bar" style={{ height: `${Math.max(item.liters > 0 ? 3 : 0, item.liters / maxDaily * 100)}%` }} /></div>
                <span className="water-bar-label">{shortDay(item.day)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="water-chart-block water-chart-block--fields">
        <h3>Consumption by field</h3>
        {analysis.fieldTotals.length === 0 ? <p className="panel__empty">Field comparison will appear when the simulator records water usage.</p> : (
          <div className="water-field-list">
            {analysis.fieldTotals.map((field) => (
              <div className="water-field-row" key={field.name}>
                <div className="water-field-row__label"><strong>{field.name}</strong><span>{formatLiters(field.liters)}</span></div>
                <div className="water-field-track"><div className="water-field-fill" style={{ width: `${field.liters / maxField * 100}%` }} /></div>
              </div>
            ))}
          </div>
        )}
      </div>
      <p className="water-panel__note">Simulation estimate, not a physical flow-meter measurement. Usage is generated when the automatic irrigation scheduler opens a field.</p>
    </section>
  );
}
