// Use the hostname that served the dashboard, with the API on port 8000.
const API_URL =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

const TOKEN_KEY = "safeagri_access_token";

export const authStore = {
  getToken() {
    try { return window.localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  setToken(token) {
    try { window.localStorage.setItem(TOKEN_KEY, token); } catch { /* storage may be disabled */ }
  },
  clearToken() {
    try { window.localStorage.removeItem(TOKEN_KEY); } catch { /* storage may be disabled */ }
  },
};

async function request(path, options = {}) {
  const token = authStore.getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
    } catch {
      detail = await res.text();
    }
    const error = new Error(`${res.status} ${path}: ${detail}`);
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  register: (payload) => request("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  me: () => request("/auth/me"),
  fields: () => request("/fields"),
  updateField: (fieldId, payload) => request(`/fields/${fieldId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  issueNodeKey: (fieldId) => request(`/fields/${fieldId}/node-key`, { method: "POST" }),
  latest: () => request("/latest"),
  alerts: () => request("/alerts"),
  syncAlerts: () => request("/alerts/sync", { method: "POST" }),
  invites: () => request("/farm/invites"),
  createInvite: () => request("/farm/invites", { method: "POST" }),
  revokeInvite: (inviteId) => request(`/farm/invites/${inviteId}`, { method: "DELETE" }),
  scheduleEvents: () => request("/schedule/events"),
  runSchedule: () => request("/schedule/run", { method: "POST" }),
};
