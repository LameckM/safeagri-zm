import React, { useCallback, useEffect, useState } from "react";
import { api, authStore } from "./api.js";
import FieldCard from "./components/FieldCard.jsx";
import StatusPill from "./components/StatusPill.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import IrrigationLog from "./components/IrrigationLog.jsx";

const POLL_MS = 10_000;

function AuthScreen({ onAuthenticated }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login({ email, password });
      authStore.setToken(result.access_token);
      onAuthenticated(result.user);
    } catch (err) {
      if (err.status === 401) authStore.clearToken();
      setError(err.status === 401
        ? "The email or password is incorrect. Check the owner credentials in backend/.env."
        : (err.message || "Unable to sign in. Check that the backend is running."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <div className="auth-brand">
          <span className="auth-brand__mark">S</span>
          <div>
            <h1>SafeAgri</h1>
            <p>SMART IRRIGATION</p>
          </div>
        </div>
        <div className="auth-intro">
          <h2>Owner sign in</h2>
          <p>Sign in to monitor the Kafubu demonstration fields and irrigation activity.</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <label>Owner email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</button>
        </form>
        <p className="auth-help">This demonstration is restricted to the configured project owner. New account registration is disabled.</p>
      </section>
    </main>
  );
}

export default function App() {
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(authStore.getToken()));
  const [fields, setFields] = useState([]);
  const [readingsByField, setReadingsByField] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [events, setEvents] = useState([]);
  const [connectionError, setConnectionError] = useState(null);
  const [checking, setChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);
  const [faultField, setFaultField] = useState("1");
  const [faultMetric, setFaultMetric] = useState("humidity");
  const [faultScenario, setFaultScenario] = useState("high");
  const [faultBusy, setFaultBusy] = useState(false);
  const [faultMessage, setFaultMessage] = useState("");

  const logout = useCallback(() => {
    authStore.clearToken();
    setUser(null);
    setFields([]);
    setReadingsByField({});
    setAlerts([]);
    setEvents([]);
    setConnectionError(null);
  }, []);

  useEffect(() => {
    if (!authStore.getToken()) return;
    let active = true;
    api.me().then((account) => {
      if (active) setUser(account);
    }).catch((err) => {
      if (err.status === 401) authStore.clearToken();
      if (active) setUser(null);
    }).finally(() => {
      if (active) setAuthLoading(false);
    });
    return () => { active = false; };
  }, []);

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
      if (err.status === 401) logout();
      else setConnectionError(err.message);
    }
  }, [logout]);

  useEffect(() => {
    if (!user) return undefined;
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [user, refresh]);

  async function handleFaultStart(event) {
    event.preventDefault();
    setFaultBusy(true);
    setFaultMessage("");
    try {
      const result = await api.startDemoFault({ field_id: Number(faultField), metric: faultMetric, scenario: faultScenario });
      setFaultMessage(`Fault active: ${result.node_id} · ${faultMetric} · ${faultScenario}`);
      await refresh();
    } catch (err) {
      setFaultMessage(err.message || "Could not start sensor fault.");
    } finally {
      setFaultBusy(false);
    }
  }

  async function handleFaultClear() {
    setFaultBusy(true);
    setFaultMessage("");
    try {
      const result = await api.clearDemoFault({ field_id: Number(faultField) });
      setFaultMessage(`Fault cleared for ${result.node_id}. Normal readings will resume.`);
      await refresh();
    } catch (err) {
      setFaultMessage(err.message || "Could not clear sensor fault.");
    } finally {
      setFaultBusy(false);
    }
  }

  async function handleCheckNow() {
    setChecking(true);
    try {
      await api.runSchedule();
      await refresh();
      setLastChecked(new Date());
    } catch (err) {
      if (err.status === 401) logout();
      else setConnectionError(err.message);
    } finally {
      setChecking(false);
    }
  }

  if (authLoading) return <main className="auth-page"><p className="auth-loading">Checking your session...</p></main>;
  if (!user) return <AuthScreen onAuthenticated={setUser} />;

  const awaitingCount = fields.filter((f) => !readingsByField[f.id]?.last_seen_at).length;
  const offlineFieldIds = new Set(alerts.filter((alert) => alert.kind === "node_offline").map((alert) => alert.field_id));
  const offlineCount = offlineFieldIds.size;

  return (
    <div className="page">
      <header className="page__header">
        <div>
          <h1>SafeAgri</h1>
          <p className="page__subtitle">{user.farm_name}{user.farm_location ? ` · ${user.farm_location}` : ""}</p>
          <p className="page__farmer">System owner: {user.full_name}</p>
        </div>
        <div className="header-actions">
          <StatusPill offlineCount={offlineCount} alertCount={alerts.length} awaitingCount={awaitingCount} />
        </div>
      </header>

      {connectionError && <div className="banner banner--error">
        Can't load farm data. Check that the backend is running.
        <span className="banner__detail">{connectionError}</span>
      </div>}

      <section className="field-grid">
        {fields.length === 0 && !connectionError && <p className="panel__empty">No fields have been added to this farm yet.</p>}
        {fields.map((field) => <FieldCard key={field.id} field={field} reading={readingsByField[field.id]} offline={offlineFieldIds.has(field.id)} />)}
      </section>

      <div className="actions">
        <button className="check-button" onClick={handleCheckNow} disabled={checking}>
          {checking ? "Checking..." : "Check irrigation now"}
        </button>
        {lastChecked && <span className="actions__note">Last manual check at {lastChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>}
      </div>

      <section className="panel demo-controls">
        <h2>Sensor fault demonstration</h2>
        <p className="panel__empty">Choose a field and inject an abnormal sensor value. The test remains active until you clear it.</p>
        <form className="demo-controls__form" onSubmit={handleFaultStart}>
          <label>Demo field
            <select value={faultField} onChange={(event) => setFaultField(event.target.value)}>
              {fields.map((field) => <option key={field.id} value={field.id}>{field.name} ({field.node_id})</option>)}
            </select>
          </label>
          <label>Sensor
            <select value={faultMetric} onChange={(event) => setFaultMetric(event.target.value)}>
              <option value="humidity">Humidity</option>
              <option value="temperature">Temperature</option>
              <option value="soil_moisture">Soil moisture / water</option>
            </select>
          </label>
          <label>Fault type
            <select value={faultScenario} onChange={(event) => setFaultScenario(event.target.value)}>
              <option value="high">Abnormally high</option>
              <option value="low">Abnormally low</option>
              <option value="flatline">Stuck / flatline</option>
            </select>
          </label>
          <button className="check-button" type="submit" disabled={faultBusy || fields.length === 0}>
            {faultBusy ? "Applying..." : "Start sensor fault"}
          </button>
          <button className="logout-button" type="button" onClick={handleFaultClear} disabled={faultBusy || fields.length === 0}>
            Clear fault / restore normal
          </button>
        </form>
        {faultMessage && <p className="demo-controls__message" role="status">{faultMessage}</p>}
      </section>

      <div className="panel-grid">
        <AlertsPanel alerts={alerts} />
        <IrrigationLog events={events} />
      </div>

      <footer className="page__footer">
        <button className="logout-button" onClick={logout}>Sign out</button>
      </footer>
    </div>
  );
}
