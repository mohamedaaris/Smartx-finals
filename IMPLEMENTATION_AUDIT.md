# FleetSync implementation audit and plan

Date: 2026-10-15. This audit precedes changes for the supplied master brief. It describes the current Vinland application; FleetSync is the requested product name, not a separate application.

## Existing architecture and evidence

| Area | Status | Current implementation and evidence | Gap |
| --- | --- | --- | --- |
| Stack and startup | Implemented and tested | `app.py` serves a Python standard-library HTTP API and static `web/` files; `run.cmd` starts it. `package.json` pins Three.js 0.180.0. There is no frontend framework, database, or WebSocket. | State is in memory; browser polls `/api/state` every 500 ms. |
| Five AMRs and task execution | Implemented and tested in software | `sim/engine.py`, `sim/models.py`, `sim/inventory.py`, and `sim/battery.py` run five named AMRs, queued work, shelf and conveyor reservations, package transfer, charging, and manual robot/slot/conveyor choices. Existing scenario tests cover end-to-end work. | No priority or due-time fields; automatic assignment is available through the legacy task API but not the main job form. No persistent ledger. |
| Navigation and traffic | Partially implemented | `sim/geometry.py` has an A* graph in Blender XY metres; `sim/engine.py` reserves edges, junctions, waiting points, shelves, conveyors, and charging bays. `sim/sensors.py` checks oriented AMR overlap and obstacle proximity. Tests exercise conflicts and recovery. | Operational routes currently use one protected passage per aisle. No validated three-lane graph, complete swept-turn collision proof, or fixed-equipment collision validation for every path. Coordinates are hard-coded. |
| Blender model and export | Implemented but not currently validated against the live scene | `blender/export_scene.py`, `blender/measure_slots.py`, and `web/assets/model_manifest.json` describe 6,097 source objects, five robot source names, 24 selected vacant board surfaces, and a 122 MB `warehouse.glb`. `web/scene.js` loads the GLB without runtime scale adjustment and maps Blender `(x,y,z)` to Three.js `(x,z,-y)`. `tests/test_model_assets.py` checks asset identity. | The live source scene was reconnected after the initial audit. Its robot poses differ from the export manifest because it has a simulation overlay; source/export parity and full physical collision geometry still need validation. The `.blend`, `.gltf`, and `.glb` assets are locally available but Git ignored. |
| Robot dimensions | Partially validated | Manifest AMR bounds are about 1.33 m wide, 2.01 m long, and 0.60 m high. `sim/geometry.py` uses 1.33 × 2.01 m and 0.15 m side clearance. | Wheel/payload protrusions, turning envelope, braking distance, and runtime collider agreement remain unmeasured. |
| Shelf inventory and scene interaction | Partially implemented | `sim/inventory.py` creates 24 logical slots tied to vacant source boards in the manifest. `sim/engine.py` is the inventory authority; `web/main.js` displays slot state and lets an occupied slot prefill retrieval. | Empty slots do not open putaway; rack/level selection and 2D/3D slot picking are absent. Slot capacity, weight, package dimensions, and hierarchy metadata are absent. Only 24 of 294 measured vacant centres are mapped. |
| Synchronized views | Partially implemented | `web/main.js` draws a 2D map from the same `/api/state` geometry and robot/task state that `web/scene.js` renders in 3D. Split view exists. Robot selection in 3D works. | 3D rack/slot selection is absent; 2D map only picks robots or places obstacles. 2D robot glyphs are symbolic rather than scaled footprints. |
| Virtual hardware and communication | Missing or partial | Battery drain/charge and a geometric 5 m detection policy are simulated. `sim/sensors.py` explicitly has no camera inference or hardware LiDAR. | Motor, encoder, IMU, odometry, camera, Wi-Fi latency/loss/disconnection, reconciliation, and physical safety interfaces are not modelled. No hardware readiness catalogue. |
| Evaluation and evidence | Partially implemented | `sim/telemetry.py` records run metrics/history; `validation/` contains prior workflow reports; `tests/` includes 34 cases; `npm run check` passes. | No equivalent stop-and-wait versus reservation-aware experiment runner. Geometry validation is not yet a full measured PASS/FAIL report. No scripted jury workflow for the new brief. |

Baseline on this host: 30 of 34 Python tests passed in the sandbox. Four HTTP tests could not connect to a local test server because socket access returned Windows error 10013; this is an execution-environment failure, not an observed application assertion failure. JavaScript syntax check passed.

## Geometry decision before editing the source scene

The configured 1.33 m AMR width and 0.15 m clearance on each side require 1.63 m for one straight lane and 4.89 m for three side-by-side lanes, before any additional separation or swept-turn allowance. Live source-scene inspection found that the 2.80/2.78/3.87 m `AISLES` figures in `sim/geometry.py` use broad bounding boxes of large end/overhead structures, not rack-to-rack obstruction at robot height. The actual shelf mesh gaps are approximately 6.3–6.7 m between columns A/B and B/C, and about 4.02 m from column C to the east boundary. Thus the inter-rack straight width check passes, while the outer C corridor fails. The full source-derived report is `validation/geometry-report.md`.

The next geometry deliverable is a candidate movement drawing and a report of collision footprint including protrusions/payload, swept turns, waiting areas, approaches, and route connectivity. A roughly 0.90 m west shift of the C rack column is a candidate for widening the outer gap while retaining more than 4.89 m between B/C. Verify its hierarchy, attached stock and fixed equipment before moving any source objects.

## File-by-file implementation plan

| File(s) | Preserve | Fix or add |
| --- | --- | --- |
| `app.py`, `run.cmd` | Existing routes, pause/reset/control semantics, HTTP serving | Add compatible endpoints for slot/rack detail, job preview, fault controls, and experiments as engine support lands. Validate request schemas and preserve legacy `/api/task` and `/api/manual-job`. |
| `sim/geometry.py` | Blender XY metre convention and A* graph interface | After source-scene redesign, load measured layout data, recompute lanes, and reject unsafe paths using footprint and swept-turn checks. Publish a machine-readable validation report. |
| `sim/models.py`, `sim/inventory.py` | Existing record IDs and one central slot ledger | Add physical slot/rack metadata, capacity limits, reservation owner, package dimensions, and product fields. Keep old IDs addressable or migrate them explicitly. |
| `sim/engine.py` | Five-AMR workflow, safe reservations, charge/traffic recovery | Add route feasibility at job creation, capacity checks, richer task lifecycle/priority, automatic versus chosen robot policy, communication failure behavior, and state reconciliation. Do this in small changes with scenario tests. |
| `sim/battery.py`, `sim/sensors.py`, `sim/telemetry.py` | Existing energy, geometric detection, and measured trace behavior | Add documented virtual hardware interfaces and sensor/odometry/communication telemetry; avoid implying physical validation. Add comparable experiment metrics. |
| `web/index.html`, `web/style.css`, `web/main.js` | Existing dashboard sections and polling data flow | Add rack/slot inspector, contextual putaway/retrieval, synchronized selection, virtual hardware/readiness views, fault controls, and measured experiment results. |
| `web/scene.js` | Original GLB loading, five source robot meshes, shared coordinates | Add selectable rack/slot regions tied to manifest IDs; validate hit priority/occlusion and show the selected slot in 3D. Update model only after Blender geometry changes. |
| `blender/measure_slots.py`, `blender/export_scene.py`, `blender/live_sync.py` | Source asset identities and non-destructive export/live overlay | Measure full physical envelope and scene hierarchy, export stable rack/slot metadata, and re-export only after verified source edits. Never overwrite the source `.blend` without validated geometry and a recoverable copy. |
| `web/assets/model_manifest.json` | Original source object mapping and measured vacant surfaces | Regenerate from the verified scene after any layout change; remove machine-specific absolute source path from portable metadata. |
| `tests/`, `scripts/`, `validation/` | Existing regression scenarios and prior evidence | Add geometry, slot picking, hardware/fault, five-robot, and baseline comparison tests; store actual run outputs, configuration, and limits. |
| `README.md`, `PROGRESS.md`, `REDESIGN.md` | Working startup and existing evidence | Update setup, architecture, geometry limits, jury walkthrough, tested capabilities, and remaining physical validation after implementation. |

## Safe sequence and gates

1. Reconnect or inspect the exact Blender source scene; measure source and runtime AMR envelopes and all relevant aisle/turn/approach geometry. Generate a geometry PASS/FAIL report and a specific rack-movement plan before source edits.
2. Change only required source geometry; regenerate GLB and manifest; update the graph and 2D drawing from one measured layout. Pass footprint, turn, station, charging, and route tests before claiming three lanes.
3. Extend the existing slot ledger and both views with the same IDs and selection state. Validate putaway/retrieval against slot capacity, inventory, and reservations.
4. Add virtual hardware and communication state behind clear interfaces, then fault injection and recovery. Build the readiness catalogue with evidence levels.
5. Add repeatable baseline/controller experiments, integrate measured output, and execute all requested scenarios. Update documentation and the jury demonstration from verified results.

After each gate, record tests, changed files, failures, and remaining limitations in `PROGRESS.md`. Do not label three-lane operation or physical hardware readiness complete until evidence supports it.
