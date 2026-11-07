# SafeAgri simulator

Start the FastAPI backend first, then run the simulator from this directory:

```powershell
python simulate.py
```

Normal mode sends readings for all four nodes every five simulated minutes.

## Independent sensor tests

Use `--sensor` to change only one measurement. Use `--node` to target one node. **All other nodes continue sending normal readings.**

| Purpose | Command |
|---|---|
| Invalid high humidity reading | `python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 0.1` |
| Temperature spike | `python simulate.py --sensor temperature --scenario spike --node node-02 --fast --hours 0.1` |
| Low soil moisture / dry-soil alert | `python simulate.py --sensor water --scenario low --node node-03 --fast --hours 0.1` |
| Hold humidity constant | `python simulate.py --sensor humidity --scenario flatline --node node-01 --fast --hours 0.1` |
| Simulate node 1 going offline | `python simulate.py --scenario offline --node node-01 --fast --hours 2` |

Sensor choices: `humidity`, `temperature`, `soil_moisture`, or `water` (alias for soil moisture).

Scenario choices: `normal`, `low`, `high`, `spike`, `flatline`, and `offline`.

- `high` and `spike` deliberately exceed physical validation limits and should create a sensor-fault alert.
- `low` changes only the selected metric. Low soil moisture triggers the existing dry-soil rule. Low humidity and low temperature are valid physical values in the current validation rules; they do not currently have agronomic warning thresholds.
- `flatline` holds only the selected metric constant. The backend flags repeated soil-moisture, temperature, and humidity values after the configured `SAFEAGRI_STUCK_RUN` count (default: four consecutive readings).
- `offline` sends one initial packet for the target node and then stops sending packets for that node. Other nodes continue normally. A new packet from the node resolves its offline alert.
- `--fast` advances each five-minute simulation step every 0.05 seconds. Without it, each step waits five real minutes.

## Accelerated offline test

The normal backend offline timeout is 15 minutes. To test offline detection quickly, stop the backend and restart it with a shorter timeout.

PowerShell (from the repository root):

```powershell
$env:SAFEAGRI_STALE_MINUTES = "0.01"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then, in a second terminal:

```powershell
cd simulator
python simulate.py --scenario offline --node node-01 --fast --hours 2
```

With a 0.01-minute timeout (0.6 seconds), node-01 should become offline while nodes 2–4 keep reporting. To test recovery, stop the offline simulation and run normal simulation again:

```powershell
python simulate.py --fast --hours 0.1
```

The offline alert should resolve after node-01 sends a new reading.

When testing is complete, restart the backend without `SAFEAGRI_STALE_MINUTES` set to restore the normal 15-minute timeout:

```powershell
Remove-Item Env:SAFEAGRI_STALE_MINUTES
```

Set `SAFEAGRI_API_URL` if the backend is not at `http://localhost:8000`, for example:

```powershell
$env:SAFEAGRI_API_URL = "http://192.168.1.20:8000"
```
