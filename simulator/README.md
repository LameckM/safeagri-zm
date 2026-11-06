# SafeAgri simulator

Run the simulator from the repository root after starting the backend:

```powershell
cd simulator
python simulate.py
```

The normal mode sends readings for all four field nodes every five simulated minutes.

## Test one sensor independently

Use `--sensor` to select exactly one metric. The other two metrics continue to send normal simulated values. Use `--node` to limit the test to one field.

| Test | Command |
|---|---|
| Humidity above physical range | `python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 1` |
| Temperature spike | `python simulate.py --sensor temperature --scenario spike --node node-02 --fast --hours 1` |
| Low soil moisture / dry-soil alert | `python simulate.py --sensor water --scenario low --node node-03 --fast --hours 1` |
| Hold humidity constant | `python simulate.py --sensor humidity --scenario flatline --node node-01 --fast --hours 1` |
| Simulate a node outage | `python simulate.py --sensor temperature --scenario offline --node node-01 --fast --hours 1` |

Available sensor names: `humidity`, `temperature`, `soil_moisture`, and `water` (alias for soil moisture).

Available scenarios: `normal`, `low`, `high`, `spike`, `flatline`, and `offline`.

- `low` uses a low reading. For soil moisture this should activate the dry-soil alert and irrigation recommendation; low humidity alone is not currently an agronomic alert threshold.
- `high` and `spike` deliberately exceed the selected sensor's physical validation range and should create a sensor-fault alert.
- `flatline` holds the selected value constant. It is logged by the simulator; a flatline alert requires the anomaly detector to be connected to the alert pipeline.
- `offline` simulates the whole node sending no packet, not just one sensor.

Use `--fast` for rapid test cycles. The simulator advances five simulated minutes per loop and waits 0.05 seconds between loops in fast mode. Without `--fast`, each loop waits five real minutes.
