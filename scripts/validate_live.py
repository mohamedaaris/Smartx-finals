"""Reset the local lab, execute a real workflow, and save its measured report.

Usage: python scripts/validate_live.py workflow
       python scripts/validate_live.py charging
This is an explicit validation action, never part of normal application startup.
"""
import argparse
import json
from pathlib import Path
import time
import urllib.request


def request(path,body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("http://127.0.0.1:8765/api/"+path,data=data,
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req,timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario",choices=("workflow","charging"))
    args = parser.parse_args()
    before = request("state")
    if any(not t["sku"].startswith("VALIDATION-") for t in before["tasks"]):
        raise SystemExit("Existing operator requests found. Export them and create a new empty run before validation.")
    request("reset",{"initial_battery":20 if args.scenario == "charging" else 100})
    request("control",{"speed":12})
    if args.scenario == "workflow":
        request("batch",{"prefix":"VALIDATION","count":5,"retrieve":True})
    request("control",{"paused":False})
    deadline = time.monotonic()+90
    while time.monotonic() < deadline:
        state = request("state")
        if state["paused"] and state["time"] > 0:
            break
        time.sleep(.5)
    else:
        request("control",{"paused":True})
        raise SystemExit("Validation deadline exceeded; inspect controller state and event stream.")
    report = request("report")
    if args.scenario == "workflow":
        assert report["metrics"]["completed"] == 10 and report["metrics"]["delivered"] == 5
        assert all(p["stage"] == "DELIVERED" for p in report["packages"])
    else:
        assert all(r["status"] == "IDLE" and r["battery"] > 25 for r in report["robots"])
        assert sum("charging at" in e["message"] for e in report["events"]) == 5
    output = Path(__file__).resolve().parents[1]/"validation"/(args.scenario+"-run.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({"scenario":args.scenario,"simulation_seconds":report["time"],
        "metrics":report["metrics"],"report":str(output)},indent=2))


if __name__ == "__main__":
    main()
