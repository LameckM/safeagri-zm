# SafeAgri

A responsive smart-irrigation monitoring and decision-support system for smallholder maize farmers in Kafubu Block, Luanshya. It combines a FastAPI backend, a React web dashboard, sensor-node credentials, irrigation rules, alerts, and a simulator.

**There is no farmer login, registration, account, password, or invite flow.** Open the dashboard directly. The dashboard is intended for a trusted local network (the same Wi-Fi or mobile hotspot as the backend computer). Sensor nodes still authenticate their readings with individual node keys.

## Project layout

- `backend/` — FastAPI API, SQLite database, and automated tests
- `dashboard/` — responsive React + Vite web dashboard
- `simulator/` — sensor simulation and targeted fault scenarios
- `ml/` — model experiments and evaluation assets

## Requirements

- Python 3.11+
- Node.js 18+ and npm
- Git

## Start the backend

From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

macOS/Linux activation: `source .venv/bin/activate`.

The API initializes SQLite and seeds four configured fields. The default database is `backend/data/irrigation.db`, resolved relative to the code rather than the terminal's current directory. Set `DB_PATH` to choose another database file. Keep your database file if you need to preserve local readings.

Check `http://localhost:8000/health`; API documentation is at `http://localhost:8000/docs`.

## Start the dashboard

In a second terminal:

```powershell
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173` on the computer. Vite listens on all network interfaces. The dashboard derives the API address from the hostname used to open the page and uses port 8000.

### Open it on a phone

1. Connect the phone and computer to the same Wi-Fi or mobile hotspot.
2. On Windows, run `ipconfig` and find the active adapter's IPv4 address.
3. On the phone, open `http://COMPUTER-IP:5173` in Safari or Chrome.
4. Ensure the backend is reachable at `http://COMPUTER-IP:8000/health`.
5. Allow inbound TCP ports 5173 and 8000 through the computer's private-network firewall.

If the dashboard opens but data does not load, check that both servers are running and that the network does not isolate connected devices.

## Simulator

Install the simulator dependency and provision the sensor keys:

```powershell
cd simulator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python provision_keys.py
python simulate.py --fast
```

The provisioning script does not ask for a farmer account. It calls the local API to issue a key for each configured node and stores them in `simulator/node_keys.json`. This file is local and must not be committed. Running provisioning again rotates the keys and invalidates the previous ones.

Examples:

```bash
python simulate.py --fast
python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 0.1
python simulate.py --sensor temperature --scenario low --node node-02 --fast --hours 0.1
python simulate.py --sensor water --scenario high --node node-03 --fast --hours 0.1
python simulate.py --scenario offline --node node-01 --fast --hours 1
```

The `SAFEAGRI_SIMULATED_FLOW_LPM` setting controls estimated water flow in litres per minute (default 12). The simulator records one water-usage entry for each automatic irrigation OPEN event, using the event duration multiplied by the configured flow rate.\n\nThe `offline` scenario sends one final baseline packet and then stops sending packets for that node. The backend marks it offline after `SAFEAGRI_STALE_MINUTES` has elapsed. The default is 15 minutes; set a shorter value for a deliberate test, then restart the backend. The simulator's `--fast` option accelerates sample generation but does not accelerate real wall-clock time used by offline detection.

Set `SAFEAGRI_API_URL` if the API is not at `http://localhost:8000`.

## Tests

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest
```

Tests use a temporary SQLite database and do not overwrite the normal local database.

## Sensor security and deployment boundary

Farmer login has intentionally been removed. Dashboard API routes are therefore unauthenticated and can be used by anyone who can reach the backend. **Keep the backend and dashboard on a trusted private network; do not expose these development services directly to the public internet.** For a public deployment, put the application behind an appropriate access-control layer and HTTPS.

Sensor readings are different: each node must send its own `X-Node-Key` header. The server stores only a SHA-256 hash of each random key. A missing or incorrect key, an unknown node, or a node without a provisioned key is rejected. The Registered fields panel can issue or rotate keys; a rotation immediately invalidates the previous key. Keep keys secret and use HTTPS outside a trusted test network.

## Monitoring and irrigation rules

- The dashboard refreshes readings, alerts, irrigation events, and the last seven days of water-use history every 10 seconds.
- The simulator records estimated litres for each automatic irrigation OPEN event using `SAFEAGRI_SIMULATED_FLOW_LPM` (default 12 L/min); these are simulated volumes, not physical meter readings.
- The backend evaluates all fields immediately when it starts, then repeats automatically every `SAFEAGRI_SCHEDULE_SECONDS` (default 60 seconds); **Check irrigation now** is an optional manual evaluation.
- Out-of-range, flatline, and implausible soil-moisture changes are marked invalid and excluded from irrigation decisions.
- Stale nodes are marked offline and are not irrigated using stale values.
- Dry-soil alerts clear when soil moisture recovers; offline alerts clear when a new packet arrives.

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DB_PATH` | `backend/data/irrigation.db` | SQLite database location |
| `SAFEAGRI_API_URL` | `http://localhost:8000` | API address used by the simulator |
| `SAFEAGRI_SCHEDULE_SECONDS` | `60` | Automatic schedule interval; `0` disables it |
| `SAFEAGRI_STALE_MINUTES` | `15` | Minutes without a packet before a node is offline |
| `SAFEAGRI_STUCK_RUN` | `4` | Consecutive identical soil-moisture readings before flatline detection |
| `SAFEAGRI_DROP_LIMIT` | `2.2` | Maximum plausible soil-moisture fall between readings |
| `SAFEAGRI_SIMULATED_FLOW_LPM` | `12` | Simulated flow rate used to estimate litres per irrigation event |

Simulated readings are test data, not field measurements. Validate thresholds with the real ESP32 sensors before using the system to guide actual irrigation.
