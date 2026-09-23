import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import FieldCard from "./components/FieldCard.jsx";
import StatusPill from "./components/StatusPill.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import IrrigationLog from "./components/IrrigationLog.jsx";

const POLL_MS = 10_000;

export default function App() {
  const [fields, setFields] = useState([]);
  const [readingsByField, setReadingsByField] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [events, setEvents] = useState([]);
  const [connectionError, setConnectionError] = useState(null);
  const [checking, setChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [fieldList, latest, alertList, eventList] = await Promise.all([
        api.fields(),
        api.latest(),
        api.alerts(),
        api.scheduleEvents(),
      ]);
      setFields(fieldList);
      const byField = {};
      for (const reading of latest) byField[reading.field_id] = reading;
      setReadingsByField(byField);
      setAlerts(alertList);
      setEvents(eventList);
      setConnectionError(null);
    } catch (err) {
      setConnectionError(err.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  async function handleCheckNow() {
    setChecking(true);
    try {
      await api.runSchedule();
      await refresh();
      setLastChecked(new Date());
    } catch (err) {
      setConnectionError(err.message);
    } finally {
      setChecking(false);
    }
  }

  const offlineCount = fields.filter((f) => {
    const r = readingsByField[f.id];
    if (!r) return true;
    const mins = (Date.now() - new Date(r.recorded_at).getTime()) / 60000;
    return mins > 15;
  }).length;

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>SafeAgri ZM</h1>
          <p className="page__subtitle">Kafubu Block, Luanshya</p>
        </div>
        <StatusPill offlineCount={offlineCount} alertCount={alerts.length} />
      </header>

      {connectionError && (
        <div className="banner banner--error">
          Can't reach the backend at the configured API URL. Check that the server is running.
          <span className="banner__detail">{connectionError}</span>
        </div>
      )}

      <section className="field-grid">
        {fields.length === 0 && !connectionError && <p className="panel__empty">Loading fields...</p>}
        {fields.map((field) => (
          <FieldCard key={field.id} field={field} reading={readingsByField[field.id]} />
        ))}
      </section>

      <div className="actions">
        <button className="check-button" onClick={handleCheckNow} disabled={checking}>
          {checking ? "Checking..." : "Check irrigation now"}
        </button>
        {lastChecked && (
          <span className="actions__note">
            Last manual check at {lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      <div className="panel-grid">
        <AlertsPanel alerts={alerts} />
        <IrrigationLog events={events} />
      </div>
    </div>
  );
}
