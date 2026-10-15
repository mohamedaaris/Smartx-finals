# Current warehouse geometry validation

Source rack and AMR bounds were measured from the open `warehouse1.blend` with `blender/audit_geometry.py`. Regenerate with `python -m scripts.validate_geometry` after new source measurements.

| Check | Required | Measured / calculated | Result |
| --- | ---: | ---: | --- |
| Source AMR width versus configured collider | 1.33 m | 1.327 m | PASS |
| Source AMR length versus configured collider | 2.01 m | 2.012 m | PASS |
| Straight single lane | 1.63 m | AMR + 0.15 m side clearance each side | DEFINITION |
| Three straight parallel lanes | 4.89 m | 3 × 1.63 m | DEFINITION |
| A/B row 1 rack-to-rack straight gap | 4.89 m | 6.61 m; margin +1.72 m | PASS (rack bounds) |
| B/C row 1 rack-to-rack straight gap | 4.89 m | 6.68 m; margin +1.79 m | PASS (rack bounds) |
| A/B row 2 rack-to-rack straight gap | 4.89 m | 6.61 m; margin +1.72 m | PASS (rack bounds) |
| B/C row 2 rack-to-rack straight gap | 4.89 m | 6.68 m; margin +1.79 m | PASS (rack bounds) |
| A/B row 3 rack-to-rack straight gap | 4.89 m | 6.61 m; margin +1.72 m | PASS (rack bounds) |
| B/C row 3 rack-to-rack straight gap | 4.89 m | 6.68 m; margin +1.79 m | PASS (rack bounds) |
| A/B row 4 rack-to-rack straight gap | 4.89 m | 6.32 m; margin +1.43 m | PASS (rack bounds) |
| B/C row 4 rack-to-rack straight gap | 4.89 m | 6.96 m; margin +2.07 m | PASS (rack bounds) |
| C/east boundary row 1 straight gap | 4.89 m | 4.02 m; margin -0.87 m | FAIL |
| C/east boundary row 2 straight gap | 4.89 m | 4.02 m; margin -0.87 m | FAIL |
| C/east boundary row 3 straight gap | 4.89 m | 4.02 m; margin -0.87 m | FAIL |
| C/east boundary row 4 straight gap | 4.89 m | 4.02 m; margin -0.87 m | FAIL |
| In-place 360° envelope, without fixed obstacles | 2.71 m | narrowest rack gap 6.32 m | UNVERIFIED: swept mesh and junctions pending |
| Waypoint graph connects pickup, packing, delivery, chargers, 12 docks | all connected | connected | PASS (graph only) |
| Source floor width | measured | 29.02 m | MEASURED |
| Full paths, fixed equipment, waiting areas, payload, braking distance | collision-free | mesh-sweep validation pending | UNVERIFIED |
| Blender unit scale | 1.0 metre convention | METRIC / 1.0 | PASS |

## Interpretation and proposed geometry change

The two inter-rack corridors have more than 4.89 m of rack-to-rack straight clearance. The C/east-boundary corridor has about 4.02 m and fails the same test. This corrects the older `sim/geometry.py` aisle figures, which use the bounding boxes of large end/overhead structures rather than rack obstruction at AMR height. Those old figures must not be presented as measured physical lane clearances.

A candidate change is to shift the C rack column and its stock about 0.90 m west while preserving the B/C gap above 4.89 m. Its exact parent hierarchy, nearby fixed objects, station approaches, turns, and full vehicle sweep must be checked before any source mesh is moved. The east wall and its approaches must remain clear. Re-export and regenerate graph/slot positions after a validated source edit.

These width tests alone do not establish three operational lanes. Continue using protected single passages until swept turns, passing, intersections, stations, and source/export parity pass.
