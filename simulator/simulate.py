"""SafeAgri simulator. Select humidity, temperature or soil moisture independently.
Examples:
 python simulate.py --sensor humidity --scenario high --node node-01 --fast --hours 1
 python simulate.py --sensor temperature --scenario spike --node node-02 --fast --hours 1
 python simulate.py --sensor water --scenario low --node node-03 --fast --hours 1
 python simulate.py --sensor humidity --scenario flatline --node node-01 --fast --hours 1
 python simulate.py --sensor temperature --scenario offline --node node-01 --fast --hours 1
"""
import argparse, logging, math, os, random, time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
 handlers=[logging.FileHandler(Path(__file__).parent/"faults.log"), logging.StreamHandler()])
log=logging.getLogger("simulator")
API_URL=f"{os.getenv('SAFEAGRI_API_URL','http://localhost:8000').rstrip('/')}/readings"
NODE_IDS=["node-01","node-02","node-03","node-04"]; INTERVAL_MIN=5

@dataclass
class FieldState:
 node_id:str; moisture:float; dry_rate:float; temp_base:float; humidity_base:float
 rain_chance_per_hour:float=0.03

def make_fields():
 return [FieldState("node-01",45,1.8,27,58),FieldState("node-02",30,2.4,29,52),FieldState("node-03",50,1.5,26,61),FieldState("node-04",22,2.1,28,55)]

def diurnal_temp(base,moment):
 hour=moment.hour+moment.minute/60
 return round(base+6*math.sin((hour-9)/24*2*math.pi)+random.uniform(-.4,.4),1)

def diurnal_humidity(base,moment):
 hour=moment.hour+moment.minute/60
 return round(max(10,min(100,base-8*math.sin((hour-9)/24*2*math.pi)+random.uniform(-1.5,1.5))),1)

def step_moisture(f,minutes):
 hours=minutes/60; value=f.moisture-f.dry_rate*hours*random.uniform(.85,1.15)
 if random.random()<f.rain_chance_per_hour*hours:
  gain=random.uniform(15,35); value+=gain; log.info("RAIN on %s: +%.1f%%",f.node_id,gain)
 f.moisture=max(2,min(100,value)); return f.moisture

def normal_reading(f,moment):
 return {"node_id":f.node_id,"soil_moisture":round(max(0,min(100,f.moisture+random.gauss(0,.15))),1),"temperature":diurnal_temp(f.temp_base,moment),"humidity":diurnal_humidity(f.humidity_base,moment),"timestamp":moment.isoformat()}

def apply_scenario(reading,sensor,scenario,held):
 if scenario=="normal": return reading
 if scenario=="offline": return None
 bounds={"humidity":(0,100,8,108),"temperature":(-5,60,-10,70),"soil_moisture":(0,100,5,110)}
 low,high,bad_low,bad_high=bounds[sensor]
 if scenario=="low": reading[sensor]=bad_low
 elif scenario in ("high","spike"): reading[sensor]=bad_high
 elif scenario=="flatline":
  key=(reading["node_id"],sensor); held.setdefault(key,reading[sensor]); reading[sensor]=held[key]
 log.info("TARGETED TEST node=%s sensor=%s scenario=%s value=%s",reading["node_id"],sensor,scenario,reading[sensor])
 return reading

def post_reading(client,reading):
 try:
  r=client.post(API_URL,json=reading,timeout=5)
  if r.status_code!=201: log.warning("API rejected: %s %s",r.status_code,r.text)
  else: log.info("POSTED %s moisture=%s temp=%s humidity=%s valid=%s",reading["node_id"],reading["soil_moisture"],reading["temperature"],reading["humidity"],r.json().get("valid"))
 except httpx.HTTPError as exc: log.error("API connection failed: %s",exc)

def run(fast=False,hours=None,sensor=None,scenario="normal",node=None):
 fields=[f for f in make_fields() if node is None or f.node_id==node]
 moment=datetime.now(timezone.utc); end=moment+timedelta(hours=hours) if hours else None
 held={}; delay=.05 if fast else INTERVAL_MIN*60
 log.info("Simulation sensor=%s scenario=%s node=%s fast=%s",sensor or "all",scenario,node or "all",fast)
 with httpx.Client() as client:
  while end is None or moment<end:
   for f in fields:
    step_moisture(f,INTERVAL_MIN); reading=normal_reading(f,moment)
    if sensor: reading=apply_scenario(reading,sensor,scenario,held)
    if reading is not None: post_reading(client,reading)
    else: log.warning("SIMULATED NODE OFFLINE: %s",f.node_id)
   moment+=timedelta(minutes=INTERVAL_MIN); time.sleep(delay)
 log.info("Simulation finished")

if __name__=="__main__":
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--fast",action="store_true")
 p.add_argument("--hours",type=float); p.add_argument("--sensor",choices=["humidity","temperature","soil_moisture","water"])
 p.add_argument("--scenario",choices=["normal","low","high","spike","flatline","offline"],default="normal")
 p.add_argument("--node",choices=NODE_IDS); a=p.parse_args()
 if a.scenario!="normal" and not a.sensor: p.error("--sensor is required for a non-normal scenario")
 run(a.fast,a.hours,"soil_moisture" if a.sensor=="water" else a.sensor,a.scenario,a.node)
