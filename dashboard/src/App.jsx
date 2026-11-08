import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import FieldCard from "./components/FieldCard.jsx";
import StatusPill from "./components/StatusPill.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import IrrigationLog from "./components/IrrigationLog.jsx";
import FieldManagement from "./components/FieldManagement.jsx";

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
      await api.syncAlerts();
      const [fieldList, latest, alertList, eventList] = await Promise.all([
        api.fields(), api.latest(), api.alerts(), api.scheduleEvents(),
      ]);
      setFields(fieldList);
      const byField = {};
      for (const reading of latest) byField[reading.field_id] = reading;
      setReadingsByField(byField);
      setAlerts(alertList);
      setEvents(eventList);
      setConnectionError(null);
    } catch (err) {
      setConnectionError(err.message || "Unable to connect to the SafeAgri API.");
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

  const awaitingCount = fields.filter((field) => !readingsByField[field.id]?.last_seen_at).length;
  const offlineFieldIds = new Set(alerts.filter((alert) => alert.kind === "node_offline").map((alert) => alert.field_id));

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>SafeAgri</h1>
          <p className="page__subtitle">AI-powered smart irrigation monitoring</p>
          <p className="page__farmer">Kafubu Block · Luanshya</p>
        </div>
        <StatusPill offlineCount={offlineFieldIds.size} alertCount={alerts.length} awaitingCount={awaitingCount} />
      </header>

      {connectionError && <div className="banner banner--error" role="alert">
        Can't load SafeAgri data. Check that the backend is running and reachable.
        <span className="banner__detail">{connectionError}</span>
        <button type="button" onClick={refresh}>Retry connection</button>
      </div>}

      <section className="field-grid">
        {fields.length === 0 && !connectionError && <p className="panel__empty">No fields are configured yet.</p>}
        {fields.map((field) => <FieldCard key={field.id} field={field} reading={readingsByField[field.id]} offline={offlineFieldIds.has(field.id)} />)}
      </section>

      <div className="actions">
        <button className="check-button" onClick={handleCheckNow} disabled={checking}>
          {checking ? "Checking..." : "Check irrigation now"}
        </button>
        {lastChecked && <span className="actions__note">Last check at {lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
      </div>

      <div className="panel-grid">
        <AlertsPanel alerts={alerts} />
        <IrrigationLog events={events} />
      </div>

      <FieldManagement fields={fields} onChanged={refresh} />

      <footer className="page__footer">Sensor data refreshes automatically every 10 seconds.</footer>
    </div>
  );
}
