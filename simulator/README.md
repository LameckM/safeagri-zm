# SafeAgri simulator

Run from the simulator directory after starting the backend:

```bash
python simulate.py
```

Normal mode sends readings for all four nodes every five simulated minutes.

## Independent sensor tests

Use `--sensor` to select one metric. Other metrics continue to report normal simulated values. Use `--node` to restrict the test to one field.

| Purpose | Command |
|---|---|
| Humidity high fault | `python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 1` |
| Temperature spike | `python simulate.py --sensor temperature --scenario spike --node node-02 --fast --hours 1` |
| Soil moisture low / dry alert | `python simulate.py --sensor water --scenario low --node node-03 --fast --hours 1` |
| Hold humidity constant | `python simulate.py --sensor humidity --scenario flatline --node node-01 --fast --hours 1` |
| Simulate node offline | `python simulate.py --sensor temperature --scenario offline --node node-01 --fast --hours 1` |

Sensor choices: `humidity`, `temperature`, `soil_moisture`, or `water` (alias for soil moisture).

Scenario choices: `normal`, `low`, `high`, `spike`, `flatline`, and `offline`.

- `high` and `spike` exceed physical validation limits and should trigger a sensor-fault alert.
- `low` sets the selected metric low. Low soil moisture triggers a dry-soil alert; humidity and temperature do not yet have agronomic warning thresholds.
- `flatline` holds only the selected metric constant and logs it. A flatline alert still requires the anomaly detector to feed the alert pipeline.
- `offline` simulates the node sending no packet.
- `--fast` advances five simulated minutes every 0.05 seconds; without it, each step waits five real minutes.

Set `SAFEAGRI_API_URL` if the backend is not at `http://localhost:8000`.
