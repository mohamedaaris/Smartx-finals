# Progress — warehouse simulation redesign

## Accepted objective

Simulate hardware warehouse operations in software and show them in the supplied
Blender model. Build an operational 3D workspace, synchronize its 2D view, and show
results only from executed controller state. Start without seeded stock or requests.
Use GPT-6 Sol for routine work and reserve Astra for major model changes or unresolved
complex problems. Verify Blender availability before continuing.

## Completed

- Reread the full master prompt and verified the live Blender 5.2.2 connection.
- Exported the original warehouse assets for the browser, preserving robot source
  IDs and respecting the source's hidden roof. Static batching and temporary robot
  optimization produce eight exported mesh groups. No blend file was saved.
- Mapped 24 inventory slots to verified vacant particle-board shelf surfaces and corrected
  AMR floor height. Conveyor approach points account for the measured front edge.
- Checked slot occupancy against 3,304 source box meshes and exact neighboring mesh
  surfaces. Found 294 vacant centres across 672 boards; source stock remains intact.
- Removed seeded inventory and automatic demo requests from application startup.
  Startup is paused. Initial battery is an explicit input, with no invented history.
- Implemented visible package storage/retrieval transfers, a timed packing stage,
  conveyor movement and delivery-confirmed outbound completion. Both 3D displays
  read the controller's package positions.
- Added request-based intake visuals because the inspected blue zone has no package
  stack. These display boxes are held during pickup and are separate from inventory.
- Redesigned the dashboard: original 3D assets, synchronized map, camera presets,
  robot inspection, sensing/routing layers, state-based workflow strip, queue,
  inventory, package journey, incident/event panels, measured charts and JSON export.
- Added parameter setup, empty reset, explicit request batches, safe queued-task
  cancellation, exclusive local port binding and automatic pause when the fleet settles.
- Fixed trapped endpoint traffic, reserved waiting-position conflicts, stale station
  admission, unsafe charging-bay diagonals and occupied charger exit/parking behavior.
  Added the existing right boundary to charging routes and restricted it from normal
  through-traffic. Charging admission protects the shared entrance.
- Added oriented footprint checks, safe segment clearance before rerouting and
  physically guarded orphan-lock recovery after a live mixed run exposed a stale
  parking reservation. The mixed charging/request regression now passes.
- Split controller records, inventory eligibility, energy estimation, sensing,
  routing and telemetry into named modules for continuation.
- Browser validation executed a real five-package cycle from empty inventory:
  10 requests completed, 5 packages delivered, minimum observed separation 2.350 m.
  All five robots also completed a separate run from 20% initial charge with two bays.
- Verified live Blender's timer and all five tracked package records. Updated the
  sync script for routes, transfers, intake, obstacle/lock graphics and charging.
- Automated validation: **23/26 tests passed**. JavaScript syntax checks passed.

## Geometry decision

The clear aisles measure 2.80 / 2.78 / 3.87 m. Three physical AMR lanes would require
4.89 m with the supplied footprint and clearance. The prompt allows a safe alternative;
the controller uses exclusive aisle passages, clear cross aisles and boundary routes.
Do not present these as three validated parallel lanes.

## Evidence and startup

- `validation/workflow-run.json`: executed browser workflow with real package history.
- `validation/charging-run.json`: executed charging run and recorded station events.
- `validation/blender-workflow.png`: original-model visual verification.
- `validation/mixed-inspection.json`: archived pre-fix diagnosis, superseded by the
  passing mixed-run regression and current controller; not a current success report.
- `run.cmd` or `python app.py`; dashboard `http://127.0.0.1:8765`.
- `blender/live_sync.py` in the original open Blender scene.

## Continuation

Read this file and README before changing the controller. Preserve source assets and
reuse the current export. Re-export only after relevant asset changes; remeasure graph
coordinates after layout edits. Rerun affected scenarios when motion or resource rules
change. Keep normal startup empty. Explicit fixtures in tests must remain separate from
application data. Extend physical turning/swept-footprint and long-workload validation
before claiming vehicle dynamics or production-grade fleet reliability.

## Operator-directed dispatch update

- The dashboard now asks the operator to choose an available AMR and either a precise
  empty shelf slot for storage, an occupied slot plus conveyor lane for delivery, or
  a station/shelf destination for a move-only job. The planned stops appear before
  assignment. The old batch and single-request API endpoints remain for integrations,
  but the site uses manual dispatch.
- Shelf routes prefer center aisle B, travel to the selected shelf row, then branch
  through the cross aisle to aisle A or C. If obstructed, the controller can use a
  safe alternate route. The measured aisles still cannot fit three abreast.
- A traffic panel shows current waits and how reservations, yielding, and rerouting
  address them. Event records include conflict and resolution messages. The 5 m
  sensing toggle now draws every AMR's radius; selected-robot sensing lists detected
  peers and obstacles.
- Default charge trigger is 30%, and Setup cannot lower it. Active work suspends at
  that threshold and resumes on the same AMR after charging. Movement at 0% is
  stopped. Charger selection avoids the occupied bay-2 access point at PARK_D.
- All 34 automated tests pass, including manual choices, center-first routing,
  charging interruption/resume, 0% immobilization and sensing. Browser verification
  on the separate test server completed one selected-slot storage job and its
  matching selected-conveyor delivery job.
