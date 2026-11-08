import React, { useCallback, useEffect, useState } from "react";
import { api, authStore } from "./api.js";
import FieldCard from "./components/FieldCard.jsx";
import StatusPill from "./components/StatusPill.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import IrrigationLog from "./components/IrrigationLog.jsx";
import TeamPanel from "./components/TeamPanel.jsx";
import FieldManagement from "./components/FieldManagement.jsx";

const POLL_MS = 10_000;

// An owner shares a link like https://dashboard/?invite=CODE. Read it once when the
// page loads, then take it out of the address bar so it is not left in history.
function readInviteFromUrl() {
  try {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("invite");
    if (code) {
      url.searchParams.delete("invite");
      window.history.replaceState({}, "", url.pathname + url.search + url.hash);
    }
    return code || "";
  } catch {
    return "";
  }
}
const INVITE_FROM_URL = readInviteFromUrl();

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState(INVITE_FROM_URL ? "register" : "login");
  // "join" uses an invite code. "setup" is only for the very first account of a deployment.
  const [path, setPath] = useState("join");
  const [form, setForm] = useState({
    full_name: "", email: "", password: "", farm_name: "", location: "", setup_key: "",
    invite_code: INVITE_FROM_URL,
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
      const account = { full_name: form.full_name, email: form.email, password: form.password };
      const result = mode === "login"
        ? await api.login({ email: form.email, password: form.password })
        : await api.register(path === "join"
          ? { ...account, invite_code: form.invite_code.trim() }
          : { ...account, farm_name: form.farm_name, location: form.location || null, setup_key: form.setup_key });
      authStore.setToken(result.access_token);
      onAuthenticated(result.user);
    } catch (err) {
      setError(err.message || "Unable to sign in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const registering = mode === "register";
  const joining = registering && path === "join";

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
          <h2>{!registering ? "Welcome back" : joining ? "Join your farm" : "Set up your farm"}</h2>
          <p>{!registering
            ? "Sign in to monitor your fields and irrigation activity."
            : joining
              ? "Enter the invite code your farm owner shared with you."
              : "Create the first account to set up this farm. You need the setup key from whoever installed SafeAgri."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {registering && <label>Full name<input name="full_name" value={form.full_name} onChange={update} autoComplete="name" required minLength={2} maxLength={100} /></label>}
          {registering && !joining && <>
            <label>Farm name<input name="farm_name" value={form.farm_name} onChange={update} required minLength={2} maxLength={120} /></label>
            <label>Farm location <span className="auth-optional">(optional)</span><input name="location" value={form.location} onChange={update} placeholder="e.g. Kafubu Block, Luanshya" maxLength={160} /></label>
          </>}
          <label>Email address<input type="email" name="email" value={form.email} onChange={update} autoComplete="email" required /></label>
          <label>Password<input type="password" name="password" value={form.password} onChange={update} autoComplete={registering ? "new-password" : "current-password"} required minLength={registering ? 10 : 1} maxLength={128} /></label>
          {joining && <label>Invite code<input name="invite_code" value={form.invite_code} onChange={update} autoComplete="off" autoCapitalize="none" spellCheck={false} required maxLength={128} /></label>}
          {registering && !joining && <label>Initial setup key<input type="password" name="setup_key" value={form.setup_key} onChange={update} autoComplete="off" required /></label>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={busy}>{busy ? "Please wait..." : !registering ? "Sign in" : joining ? "Join farm" : "Create farm account"}</button>
        </form>
        <p className="auth-switch">
          {!registering ? "Have an invite code?" : "Already have an account?"}
          {" "}<button type="button" onClick={() => { setMode(registering ? "login" : "register"); setPath("join"); setError(""); }}>
            {!registering ? "Join a farm" : "Sign in"}
          </button>
        </p>
        {registering && <p className="auth-switch auth-switch--small">
          <button type="button" onClick={() => { setPath(joining ? "setup" : "join"); setError(""); }}>
            {joining ? "First time installing SafeAgri? Set up the farm" : "Have an invite code instead?"}
          </button>
        </p>}
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
          <p className="page__farmer">{user.role === "member" ? "Team member" : "Farmer"}: {user.full_name}</p>
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

      <div className="panel-grid">
        <AlertsPanel alerts={alerts} />
        <IrrigationLog events={events} />
      </div>

      {user.role !== "member" && <>
        <FieldManagement fields={fields} onChanged={refresh} />
        <TeamPanel />
      </>}

      <footer className="page__footer">
        <button className="logout-button" onClick={logout}>Sign out</button>
      </footer>
    </div>
  );
}
