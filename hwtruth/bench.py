"""Paired A/B benchmark harness for fan curves (and any LACT setting).

The rule that makes it science: change ONE variable, run the same load,
restore the previous state automatically, and judge the delta against the
noise you have already seen. Synthetic loads saturate around 110 W on a
250 W card — the decisive numbers come from real games.
"""
import json
import statistics
import subprocess
import time

from . import lact

TELEMETRY_QUERY = ("clocks.current.graphics,clocks.current.memory,temperature.gpu,"
                   "power.draw,fan.speed,utilization.gpu")


def measure(tag, load, instances, seconds, out_file=None):
    procs = [subprocess.Popen(load, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             for _ in range(instances)]
    rows = []
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < seconds:
            row = subprocess.check_output(
                ["nvidia-smi", f"--query-gpu={TELEMETRY_QUERY}", "--format=csv,noheader,nounits"],
                text=True, timeout=10).strip()
            rows.append([v.strip() for v in row.split(",")])
            if out_file:
                out_file.write(",".join(rows[-1]) + "\n")
                out_file.flush()
            time.sleep(2)
    finally:
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait(timeout=10)
    steady = rows[60:] if len(rows) > 70 else rows  # skip warm-up
    return {
        "tag": tag,
        "core_mhz_median": statistics.median(float(r[0]) for r in steady),
        "temp_c_median": statistics.median(float(r[2]) for r in steady),
        "temp_c_max": max(float(r[2]) for r in steady),
        "watts_median": statistics.median(float(r[3]) for r in steady),
        "fan_pct_median": statistics.median(float(r[4]) for r in steady),
    }


def set_curve(curve):
    gpu = _first_gpu()
    config = lact.request("get_gpu_config", {"id": gpu})
    old = json.loads(json.dumps(config["fan_control_settings"]))
    config["fan_control_settings"]["curve"] = {int(k): v for k, v in curve.items()}
    lact.request("set_gpu_config", {"id": gpu, "config": config})
    return old


def _first_gpu():
    devices = lact.request("list_devices")
    if isinstance(devices, list) and devices:
        return devices[0]
    if isinstance(devices, dict):
        return next(iter(devices))
    raise RuntimeError("no GPU reported by LACT")


def run_ab(curve_a, curve_b, load, instances=3, seconds=300, out_dir=None):
    """Run curve A then curve B on the same load; restore curve A after."""
    results = {}
    for tag, curve in (("A", curve_a), ("B", curve_b)):
        set_curve(curve)
        time.sleep(15)
        fh = out_dir.open(f"ab-{tag}-telemetry.csv", "w") if out_dir else None
        try:
            results[tag] = measure(tag, load, instances, seconds, fh)
        finally:
            if fh:
                fh.close()
        print(json.dumps(results[tag]), flush=True)
    set_curve(curve_a)
    results["delta_core_mhz"] = results["B"]["core_mhz_median"] - results["A"]["core_mhz_median"]
    results["restored"] = "A"
    return results
