"""Validate measured source rack clearances; leave unmeasured motion claims open."""

from __future__ import annotations

import json
from math import hypot
from pathlib import Path

from sim.geometry import ROBOT_LENGTH, ROBOT_WIDTH, SIDE_CLEARANCE, NavigationGraph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "validation/source-geometry.json"
OUTPUT = ROOT / "validation/geometry-report.md"


def report() -> str:
    if not SOURCE.exists():
        raise RuntimeError("Run blender/audit_geometry.py in the open source scene first")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    racks = source["racks"]
    graph = NavigationGraph()
    observed = []
    for robot in source["robots"].values():
        a, b, _, c, d, _ = robot["bounds"]
        observed.append((min(c-a, d-b), max(c-a, d-b)))
    observed_width = max(w for w, _ in observed)
    observed_length = max(l for _, l in observed)
    single = ROBOT_WIDTH + 2 * SIDE_CLEARANCE
    triple = 3 * single
    rotation = hypot(ROBOT_WIDTH, ROBOT_LENGTH) + 2 * SIDE_CLEARANCE
    floor = source["floor_bounds"]
    floor_width = floor[3] - floor[0]
    corridors = {}
    for row in range(1, 5):
        a, b, c = (racks[f"{col}R{row}"]["bounds"] for col in "ABC")
        corridors[f"A/B row {row}"] = b[0] - a[3]
        corridors[f"B/C row {row}"] = c[0] - b[3]
    # The right-side wall is the existing navigation boundary. A full mesh
    # clearance check is still needed before treating this as a route.
    east = {f"C/east boundary row {row}": 9.04 - racks[f"CR{row}"]["bounds"][3]
            for row in range(1, 5)}
    stations = ["PICKUP", "PACKING", "DELIVERY", "CHARGE_1", "CHARGE_2"]
    shelf_nodes = [f"{col}R{row}" for col in "ABC" for row in range(1, 5)]
    connected = all(graph.path("PICKUP", goal) for goal in stations + shelf_nodes)
    lines = [
        "# Current warehouse geometry validation",
        "",
        "Source rack and AMR bounds were measured from the open `warehouse1.blend` with `blender/audit_geometry.py`. Regenerate with `python -m scripts.validate_geometry` after new source measurements.",
        "",
        "| Check | Required | Measured / calculated | Result |",
        "| --- | ---: | ---: | --- |",
        f"| Source AMR width versus configured collider | {ROBOT_WIDTH:.2f} m | {observed_width:.3f} m | {'PASS' if abs(observed_width-ROBOT_WIDTH)<.02 else 'FAIL'} |",
        f"| Source AMR length versus configured collider | {ROBOT_LENGTH:.2f} m | {observed_length:.3f} m | {'PASS' if abs(observed_length-ROBOT_LENGTH)<.02 else 'FAIL'} |",
        f"| Straight single lane | {single:.2f} m | AMR + 0.15 m side clearance each side | DEFINITION |",
        f"| Three straight parallel lanes | {triple:.2f} m | 3 × {single:.2f} m | DEFINITION |",
    ]
    for name, width in corridors.items():
        lines.append(f"| {name} rack-to-rack straight gap | {triple:.2f} m | {width:.2f} m; margin {width-triple:+.2f} m | {'PASS (rack bounds)' if width>=triple else 'FAIL'} |")
    for name, width in east.items():
        lines.append(f"| {name} straight gap | {triple:.2f} m | {width:.2f} m; margin {width-triple:+.2f} m | {'PASS (rack bounds)' if width>=triple else 'FAIL'} |")
    lines += [
        f"| In-place 360° envelope, without fixed obstacles | {rotation:.2f} m | narrowest rack gap {min(corridors.values()):.2f} m | UNVERIFIED: swept mesh and junctions pending |",
        f"| Waypoint graph connects pickup, packing, delivery, chargers, 12 docks | all connected | {'connected' if connected else 'disconnected'} | {'PASS (graph only)' if connected else 'FAIL'} |",
        f"| Source floor width | measured | {floor_width:.2f} m | MEASURED |",
        "| Full paths, fixed equipment, waiting areas, payload, braking distance | collision-free | mesh-sweep validation pending | UNVERIFIED |",
        f"| Blender unit scale | 1.0 metre convention | {source['unit_system']} / {source['unit_scale']} | {'PASS' if source['unit_system']=='METRIC' and source['unit_scale']==1 else 'UNVERIFIED'} |",
        "",
        "## Interpretation and proposed geometry change",
        "",
        "The two inter-rack corridors have more than 4.89 m of rack-to-rack straight clearance. The C/east-boundary corridor has about 4.02 m and fails the same test. This corrects the older `sim/geometry.py` aisle figures, which use the bounding boxes of large end/overhead structures rather than rack obstruction at AMR height. Those old figures must not be presented as measured physical lane clearances.",
        "",
        "A candidate change is to shift the C rack column and its stock about 0.90 m west while preserving the B/C gap above 4.89 m. Its exact parent hierarchy, nearby fixed objects, station approaches, turns, and full vehicle sweep must be checked before any source mesh is moved. The east wall and its approaches must remain clear. Re-export and regenerate graph/slot positions after a validated source edit.",
        "",
        "These width tests alone do not establish three operational lanes. Continue using protected single passages until swept turns, passing, intersections, stations, and source/export parity pass.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.write_text(report(), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
