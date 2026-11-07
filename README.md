# SafeAgri ZM

A smart irrigation monitoring and decision-support system for smallholder maize fields in Kafubu Block, Luanshya. The project combines a FastAPI backend, a React web dashboard, and a sensor simulator while ESP32 hardware integration is being developed.

The dashboard is a responsive website. Open it from a desktop, Android phone, or iPhone browser; no Expo Go installation or separate mobile application is required.

## Project structure

```text
safeagri-zm/
├── backend/       # FastAPI API, SQLite database, and tests
├── dashboard/     # Responsive React + Vite web dashboard
├── ml/            # Machine-learning experiments and supporting work
└── simulator/     # Simulated readings and sensor fault injection
```

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer and npm
- Git

## 1. Configure the project owner (first installation)

Owner login is configured in one local file, `backend/.env`. Public registration is disabled. From the repository root in PowerShell:

```powershell
Copy-Item backend/.env.example backend/.env
notepad backend/.env
```

Set your own `SAFEAGRI_OWNER_EMAIL`, `SAFEAGRI_OWNER_PASSWORD` (at least 10 characters), and `SAFEAGRI_SECRET_KEY` (a long random secret). Keep the same secret between restarts. The backend creates or updates the single owner account at startup, so the credentials in this file are the credentials accepted by the login screen. You can change the owner email or password in this file and restart the backend to apply the change.

The database is always stored at `backend/data/irrigation.db`, regardless of which directory you use to start Uvicorn. Keep this file to preserve readings and fields.

## 2. Start the backend

Open a terminal in the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On macOS/Linux, activate the environment with:

```bash
source .venv/bin/activate
```

The API initializes its SQLite database and seeds the four configured fields when it starts. The default database is created at `backend/data/irrigation.db`; keep this file if you need to preserve local readings.

Check the API on the computer at [http://localhost:8000/health](http://localhost:8000/health) or open the interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## 3. Start the web dashboard

Open a second terminal from the repository root:

```powershell
cd dashboard
npm install
npm run dev
```

Vite listens on all network interfaces at port `5173`. On the same computer, open [http://localhost:5173](http://localhost:5173).

The dashboard automatically builds its API address from the hostname used in the browser, with port `8000`. For example, when a phone opens `http://192.168.1.20:5173`, its API requests go to `http://192.168.1.20:8000`. The optional `dashboard/.env` file is not required. If you need a different API host, copy `.env.example` to `.env`, set `VITE_API_URL`, and restart Vite.

## 4. Open the dashboard on a phone

1. Connect the computer running the backend and dashboard to the same Wi-Fi network or mobile hotspot as the phone.
2. Find the computer's local IPv4 address:
   - Windows: run `ipconfig` and read the IPv4 address under the active Wi-Fi adapter.
   - macOS/Linux: use `ip addr` or the network settings.
3. On the phone, open Safari (iPhone) or Chrome (Android) and visit `http://COMPUTER-IP:5173`, replacing `COMPUTER-IP` with that address.
4. Keep both terminal processes running while using the dashboard.

If the page opens but data does not load, check that the backend is running and that the phone can reach `http://COMPUTER-IP:8000/health`. Allow inbound TCP ports `5173` and `8000` through the computer's firewall on the private network. Some mobile hotspots or Wi-Fi networks isolate connected devices; if so, use a network that permits device-to-device communication.

The backend CORS policy permits localhost and private-network IPv4 origins for local development/demo use. This is not production authentication or internet-facing security. Do not expose the development servers directly to the public internet.

## 5. Automatic demonstration sensors and controls

The backend starts the four simulated sensor nodes automatically. They produce changing soil-moisture, temperature, and humidity readings every five seconds by default. No separate simulator terminal, farmer registration, or node-key provisioning is needed for the defence demonstration.

Use the dashboard's **Sensor fault demonstration** panel to choose Field 1–4, select humidity, temperature, or soil moisture, then apply an abnormally high, abnormally low, or stuck/flatline value. The injected fault remains active until you select **Clear fault / restore normal**. Normal readings resume after clearing, and sensor-fault alerts resolve once the incoming values pass validation.

Node connectivity is deliberately controlled only from a terminal. Run these commands from the repository root:

```powershell
python -m backend.node_control node-01 offline
python -m backend.node_control node-01 online
```

Replace `node-01` with `node-02`, `node-03`, or `node-04`. Offline status is stored and its node-offline alert is synchronized immediately by the command. Setting a node online clears the offline alert immediately; simulated readings resume on the next five-second cycle.

Optional demo settings:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SAFEAGRI_DEMO_SIMULATION` | `1` | Set to `0` to disable automatic demo readings. |
| `SAFEAGRI_DEMO_INTERVAL_SECONDS` | `5` | Seconds between simulated sensor packets. |
| `SAFEAGRI_OWNER_EMAIL` | `owner@example.com` | Example owner email; set it in `backend/.env`. |
| `SAFEAGRI_OWNER_PASSWORD` | No default | Set a private password in `backend/.env`. |
| `SAFEAGRI_OWNER_NAME` | `SafeAgri Owner` | Owner display name. |
| `SAFEAGRI_FARM_NAME` | `Kafubu Demonstration Farm` | Dashboard farm label. |
| `SAFEAGRI_FARM_LOCATION` | `Kafubu Block, Luanshya` | Dashboard location label. |

The automatic simulator is demonstration data, not live ESP32 telemetry. Real hardware integration remains a later stage.

## 6. Run backend tests

From the repository root:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

The tests use a temporary SQLite database; they do not need to overwrite the normal local database.

## Sensor node keys (for later ESP32 integration)

The automatic defence simulator writes demo readings directly to the local database. The protected sensor-reading API remains available for the later hardware stage. Every real device reading must carry that node's key in an `X-Node-Key` header. Without it anyone who can reach the API could post fake moisture values and steer irrigation decisions.

The project owner issues a key with `POST /fields/{field_id}/node-key`. The response contains the key once and the server keeps only its hash, so write it into the device firmware securely. Issuing a new key for a field immediately stops the old one working. `GET /fields` shows `has_node_key` for each field but never the key.

A device sends, for example:

```
POST /readings
X-Node-Key: sak_...
Content-Type: application/json

{"node_id": "node-01", "soil_moisture": 41.2, "temperature": 27.5, "humidity": 58}
```

A reading with a missing or wrong key, an unknown `node_id`, or a node that has no key yet all get the same `401`, so the API does not reveal which node IDs exist. The server log records which of those it was.

Upgrading an existing database adds the key column automatically, but every node starts with no key and is rejected until you issue one. `POST /alerts/sync` requires the project owner's login and only touches the owner's demonstration fields.

Keys travel in a plain header, so anything on the network path can read them over HTTP. Put the API behind HTTPS before any device reports over a network you do not control.

## Irrigation scheduling and sensor checks

The backend evaluates every field on a timer, so irrigation decisions do not wait for the dashboard's "Check irrigation now" button. The button still works for an immediate check.

Incoming sensor readings are checked for physical limits and repeated-value faults. Soil moisture also has an implausible-drop check. A reading that fails any check is stored but marked invalid, excluded from irrigation decisions, and raises a sensor alert:

- Out of range: a value outside the sensor's physical limits (all three metrics).
- Flatline: the same soil moisture, temperature, or humidity value several readings in a row.
- Implausible drop: soil moisture falling faster than soil can dry. Rises from rain or irrigation are normal and never flagged.

The soil-moisture drop rule and its flatline rule are based on the experiments in `ml/`. Temperature and humidity flatlines use the same configurable consecutive-reading count. These environment variables tune them:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SAFEAGRI_SCHEDULE_SECONDS` | `60` | Seconds between automatic irrigation checks. `0` turns the loop off. |
| `SAFEAGRI_STUCK_RUN` | `4` | Identical readings for any monitored metric in a row that count as a flatline. |
| `SAFEAGRI_DROP_LIMIT` | `2.2` | Largest soil moisture fall (percentage points) between readings before it is flagged. |
| `SAFEAGRI_STALE_MINUTES` | `15` | Minutes without a packet before a node is offline. The drop rule is also skipped across gaps longer than this. |

The flatline default was tuned on simulated data at 0.1% resolution. If the real ESP32 reports whole-number percentages, raise `SAFEAGRI_STUCK_RUN` or slow drying will trigger false flatline alerts.

## Notes

- The responsive web dashboard is the supported phone interface; the separate Expo `mobile-dashboard/` application has been retired.
- Local virtual environments, Node dependencies, environment files, databases, and generated logs are excluded from Git. Recreate dependencies using the requirements and package lock files.
- The current irrigation decision flow includes rule-based scheduling. Treat simulated readings as test data, not field measurements.
