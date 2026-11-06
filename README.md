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

The API initializes its SQLite database and seeds the four configured fields when it starts. The default database is created at `backend/data/irrigation.db`; keep this file if you need to preserve local readings.

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
python simulate.py --fast
```

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

## Notes

- The responsive web dashboard is the supported phone interface; the separate Expo `mobile-dashboard/` application has been retired.
- Local virtual environments, Node dependencies, environment files, databases, and generated logs are excluded from Git. Recreate dependencies using the requirements and package lock files.
- The current irrigation decision flow includes rule-based scheduling. Treat simulated readings as test data, not field measurements.
