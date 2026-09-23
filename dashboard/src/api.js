const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${path}: ${body}`);
  }
  return res.json();
}

export const api = {
  fields: () => request("/fields"),
  latest: () => request("/latest"),
  alerts: () => request("/alerts"),
  scheduleEvents: () => request("/schedule/events"),
  runSchedule: () => request("/schedule/run", { method: "POST" }),
};
