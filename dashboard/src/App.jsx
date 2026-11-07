import React, { useCallback, useEffect, useState } from "react";
import { api, authStore } from "./api.js";
import FieldCard from "./components/FieldCard.jsx";
import StatusPill from "./components/StatusPill.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import IrrigationLog from "./components/IrrigationLog.jsx";

const POLL_MS = 10_000;

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({
    full_name: "", email: "", password: "", farm_name: "", location: "", setup_key: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function update(event) {
    setForm((old) => ({ ...old, [event.target.name]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = mode === "login"
        ? await api.login({ email: form.email, password: form.password })
        : await api.register({
            full_name: form.full_name,
            email: form.email,
            password: form.password,
            farm_name: form.farm_name,
            location: form.location || null,
            ...(form.setup_key ? { setup_key: form.setup_key } : {}),
          });
      authStore.setToken(result.access_token);
      onAuthenticated(result.user);
    } catch (err) {
      setError(err.message || "Unable to sign in. Please try again.");
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
          <h2>{mode === "login" ? "Welcome back" : "Create your farm account"}</h2>
          <p>{mode === "login"
            ? "Sign in to monitor your fields and irrigation activity."
            : "Set up your farm workspace to start monitoring your fields."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && <>
            <label>Full name<input name="full_name" value={form.full_name} onChange={update} autoComplete="name" required minLength={2} maxLength={100} /></label>
            <label>Farm name<input name="farm_name" value={form.farm_name} onChange={update} required minLength={2} maxLength={120} /></label>
            <label>Farm location <span className="auth-optional">(optional)</span><input name="location" value={form.location} onChange={update} placeholder="e.g. Kafubu Block, Luanshya" maxLength={160} /></label>
          </>}
          <label>Email address<input type="email" name="email" value={form.email} onChange={update} autoComplete="email" required /></label>
          <label>Password<input type="password" name="password" value={form.password} onChange={update} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={mode === "register" ? 10 : 1} maxLength={128} /></label>
          {mode === "register" && <>
            <label>Initial setup key <span className="auth-optional">(first account only)</span><input type="password" name="setup_key" value={form.setup_key} onChange={update} autoComplete="off" /></label>
            <p className="auth-help">The farm administrator must provide this key when creating the first account. Later registrations do not need it.</p>
          </>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <p className="auth-switch">
          {mode === "login" ? "New to SafeAgri?" : "Already have an account?"}
          {" "}<button type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </button>
        </p>
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
        </div>
        <div className="header-actions">
          <span className="account-label">{user.full_name}</span>
          <button className="logout-button" onClick={logout}>Sign out</button>
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

      <div className="panel-grid">
        <AlertsPanel alerts={alerts} />
        <IrrigationLog events={events} />
      </div>
    </div>
  );
}
