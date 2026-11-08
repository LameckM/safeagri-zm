// Use the hostname that served the dashboard, with the API on port 8000.
const API_URL = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`;

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
    } catch { detail = await res.text(); }
    const error = new Error(`${res.status} ${path}: ${detail}`);
    error.status = res.status;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  fields: () => request("/fields"),
  updateField: (id, payload) => request(`/fields/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  issueNodeKey: (id) => request(`/fields/${id}/node-key`, { method: "POST" }),
  latest: () => request("/latest"),
  alerts: () => request("/alerts"),
  syncAlerts: () => request("/alerts/sync", { method: "POST" }),
  scheduleEvents: () => request("/schedule/events"),
  runSchedule: () => request("/schedule/run", { method: "POST" }),
};
