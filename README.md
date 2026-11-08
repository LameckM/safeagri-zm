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

## 1. Start the backend

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

The API initializes its SQLite database and seeds the four configured fields when it starts. The default database is `backend/data/irrigation.db` next to the code, wherever you start the server from, and it is not committed to git. Keep this file if you need to preserve local readings. Set `DB_PATH` to use a different file.

Check the API on the computer at [http://localhost:8000/health](http://localhost:8000/health) or open the interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## 2. Start the web dashboard

Open a second terminal from the repository root:

```powershell
cd dashboard
npm install
npm run dev
```

Vite listens on all network interfaces at port `5173`. On the same computer, open [http://localhost:5173](http://localhost:5173).

The dashboard automatically builds its API address from the hostname used in the browser, with port `8000`. For example, when a phone opens `http://192.168.1.20:5173`, its API requests go to `http://192.168.1.20:8000`. The optional `dashboard/.env` file is not required. If you need a different API host, copy `.env.example` to `.env`, set `VITE_API_URL`, and restart Vite.

## 3. Open the dashboard on a phone

1. Connect the computer running the backend and dashboard to the same Wi-Fi network or mobile hotspot as the phone.
2. Find the computer's local IPv4 address:
   - Windows: run `ipconfig` and read the IPv4 address under the active Wi-Fi adapter.
   - macOS/Linux: use `ip addr` or the network settings.
3. On the phone, open Safari (iPhone) or Chrome (Android) and visit `http://COMPUTER-IP:5173`, replacing `COMPUTER-IP` with that address.
4. Keep both terminal processes running while using the dashboard.

If the page opens but data does not load, check that the backend is running and that the phone can reach `http://COMPUTER-IP:8000/health`. Allow inbound TCP ports `5173` and `8000` through the computer's firewall on the private network. Some mobile hotspots or Wi-Fi networks isolate connected devices; if so, use a network that permits device-to-device communication.

The backend CORS policy permits localhost and private-network IPv4 origins for local development/demo use. This is not production authentication or internet-facing security. Do not expose the development servers directly to the public internet.

## 4. Run the sensor simulator (optional)

With the backend running, open another terminal:

```powershell
cd simulator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SAFEAGRI_EMAIL = "you@example.com"
python provision_keys.py
python simulate.py --fast
```

The backend only accepts readings from nodes that present a key (see "Sensor node keys" below). `provision_keys.py` logs in as your farmer account, issues a key for every field, and saves them to `simulator/node_keys.json`, which is not committed. You only need to run it once, or again to rotate the keys.

Use `python simulate.py` for the five-minute real-time interval, or `python simulate.py --hours 24` to stop after 24 simulated hours. The simulator sends readings to `http://localhost:8000` by default. Set `SAFEAGRI_API_URL` if the API is running elsewhere:

```powershell
$env:SAFEAGRI_API_URL = "http://192.168.1.20:8000"
python simulate.py --fast
```

Generated fault logs are local and are not committed.

## 5. Run backend tests

From the repository root:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

The tests use a temporary SQLite database; they do not need to overwrite the normal local database.

## Accounts and team invites

Two environment variables must be set before the backend starts:

| Variable | Meaning |
| --- | --- |
| `SAFEAGRI_SECRET_KEY` | Long random secret used to sign login tokens. The server refuses to start without it. |
| `SAFEAGRI_INITIAL_SETUP_KEY` | One-time key that authorizes the very first account. Needed only once. |

The first account is created from the sign-in page with "Join a farm", then "First time installing SafeAgri? Set up the farm". It needs the setup key, creates the farm, and becomes its owner with the four configured fields.

Nobody else can create an account on their own. The owner opens the dashboard, goes to the Team panel, and presses "Create invite". That gives a link and a code for one person, shown once, valid for 7 days (`SAFEAGRI_INVITE_DAYS` changes this). The invited person opens the link, or enters the code under "Join a farm", and joins the owner's farm as a team member with the same fields, alerts and history. Used, expired and revoked codes all get the same refusal.

Team members can watch the dashboard and run an irrigation check. Only the owner can invite people, rename fields and issue sensor keys, because rotating a key cuts that sensor off until it is updated.

## Sensor node keys

Every reading must carry the key of the node that sent it, in an `X-Node-Key` header. Without it anyone who can reach the API could post fake moisture values and steer irrigation decisions.

The owner issues a key from the dashboard (Registered fields, then "Issue key"), by running `simulator/provision_keys.py`, or with `POST /fields/{field_id}/node-key`. The response contains the key once and the server keeps only its hash, so write it into the device firmware straight away. Issuing a new key for a field immediately stops the old one working. `GET /fields` shows `has_node_key` for each field but never the key.

A device sends, for example:

```
POST /readings
X-Node-Key: sak_...
Content-Type: application/json

{"node_id": "node-01", "soil_moisture": 41.2, "temperature": 27.5, "humidity": 58}
```

A reading with a missing or wrong key, an unknown `node_id`, or a node that has no key yet all get the same `401`, so the API does not reveal which node IDs exist. The server log records which of those it was.

Upgrading an existing database adds the key column automatically, but every node starts with no key and is rejected until you issue one. `POST /alerts/sync` now requires a farmer login and only touches that farmer's own fields.

Keys travel in a plain header, so anything on the network path can read them over HTTP. Put the API behind HTTPS before any device reports over a network you do not control.

## Irrigation scheduling and sensor checks

The backend evaluates every field on a timer, so irrigation decisions do not wait for the dashboard's "Check irrigation now" button. The button still works for an immediate check.

Incoming soil moisture readings are checked for three kinds of fault. A reading that fails any check is stored but marked invalid, excluded from decisions, and raises a sensor alert:

- Out of range: a value outside the sensor's physical limits (all three metrics).
- Flatline: the same soil moisture value several readings in a row.
- Implausible drop: soil moisture falling faster than soil can dry. Rises from rain or irrigation are normal and never flagged.

The flatline and drop rules come from the experiments in `ml/`, where they outperformed the anomaly model. They apply to soil moisture only. These environment variables tune them:

| Variable | Default | Meaning |
| --- | --- | --- |
| `SAFEAGRI_SCHEDULE_SECONDS` | `60` | Seconds between automatic irrigation checks. `0` turns the loop off. |
| `SAFEAGRI_STUCK_RUN` | `4` | Identical moisture readings in a row that count as a flatline. |
| `SAFEAGRI_DROP_LIMIT` | `2.2` | Largest soil moisture fall (percentage points) between readings before it is flagged. |
| `SAFEAGRI_STALE_MINUTES` | `15` | Minutes without a packet before a node is offline. The drop rule is also skipped across gaps longer than this. |

The flatline default was tuned on simulated data at 0.1% resolution. If the real ESP32 reports whole-number percentages, raise `SAFEAGRI_STUCK_RUN` or slow drying will trigger false flatline alerts.

## Notes

- The responsive web dashboard is the supported phone interface; the separate Expo `mobile-dashboard/` application has been retired.
- Local virtual environments, Node dependencies, environment files, databases, and generated logs are excluded from Git. Recreate dependencies using the requirements and package lock files.
- The current irrigation decision flow includes rule-based scheduling. Treat simulated readings as test data, not field measurements.
