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
  The original validation run used two bays; the current controller uses five
  dedicated charging/depot positions in the extended Blender zone.
- Verified live Blender's timer and all five tracked package records. Updated the
  sync script for routes, transfers, intake, obstacle/lock graphics and charging.
- Automated validation: **23/26 tests passed**. JavaScript syntax checks passed.

## Geometry decision

The earlier 2.80 / 2.78 / 3.87 m figures came from broad end/overhead object bounds,
not rack-to-rack clearance at robot height. Reinspection of the live source scene
measured conservative straight gaps of 6.31 / 6.66 / 4.02 m. Three nominal lanes
require 4.89 m with the supplied footprint and clearance. West and middle pass that
straight-width check; east fails. Turns, passing, fixed equipment and station
approaches remain unvalidated. The controller still uses exclusive passages and
must not be presented as three operational parallel lanes.

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
  stopped. Each robot now charges at its own depot position in the extended area.
- All 36 automated tests pass, including manual choices, center-first routing,
  charging interruption/resume, 0% immobilization and sensing. Browser verification
  on the separate test server completed one selected-slot storage job and its
  matching selected-conveyor delivery job.

## 2026-10-15 master brief continuation

- Audited the existing application in `IMPLEMENTATION_AUDIT.md` and documented a
  source-scene geometry proposal in `GEOMETRY_PLAN.md` before moving any objects.
- Reconnected live Blender 5.2.2 and measured 12 rack groups and five source robots
  with `blender/audit_geometry.py`. Source measurements and the generated PASS/FAIL
  report are in `validation/source-geometry.json` and `validation/geometry-report.md`.
- Corrected the previous aisle widths, which used end/overhead structure bounds.
  The source rack-to-rack straight gaps are 6.31 / 6.66 / 4.02 m at their narrowest;
  three nominal lanes need 4.89 m. The east corridor fails. The graph and controller
  still operate with exclusive passages; no three-lane claim is made.
- Added source-board, vacancy validation and package-capacity metadata to the
  authoritative slot records. Unvalidated slots are rejected for putaway.
- Added a shared selected-slot inspector and contextual putaway/retrieval planning.
  The 2D map and 3D view use the same slot IDs as the backend. Browser checks
  confirmed 2D selection and empty-slot putaway prefill; 3D picking still needs
  an interaction check from a visible shelf angle.
- The complete 34-test Python suite and JavaScript syntax check pass. No original
  Blender asset was moved or saved; swept turns, fixed equipment, stock hierarchy,
  and real three-lane traffic behavior remain to be validated before geometry edits.

## Extended charging and depot area

- Measured the user's updated `Plane.003` in live Blender: X −18.18 to 9.01 m,
  Y −49.40 to −43.57 m. The controller and dashboard now treat that complete
  footprint as the combined charging and depot area.
- Five separated `DEPOT_1` through `DEPOT_5` positions are each charging-capable.
  Straight entry branches connect them to the south cross aisle; an idle AMR
  outside the marked area returns to its own depot position after queued jobs
  have had a chance to claim it. An AMR already docked at a clear point inside
  the area may stay there and charge.
- A depot-bound AMR with more than 30% battery can take a newly assigned order
  immediately. At or below 30%, it heads to its depot charger. Task energy
  estimates now include the return to that robot's depot.
- All 36 Python tests pass with localhost access, including depot diversion and
  simultaneous five-AMR charging. The minimum separation in a separate five-AMR
  charging run was 2.40 m.

## Charging across the full green area

- Charging is triggered by being stationary and unassigned anywhere within the
  measured green charging area, rather than by occupying one named pad. The
  five depot positions remain the controller's separated, safe return stops;
  a stop that obstructs a depot approach is moved to a clear position.
- Idle AMRs continue topping up at the depot from 85% to 100% and remain
  available for new work above 30%. Automatic run pause waits until this idle
  top-up finishes. The dashboard reports idle charging separately from travel.
- The 3D view now marks all five depot stops with visible green pads and
  `CHARGE 1` through `CHARGE 5` labels. Clicking a pad shows its occupancy and
  charging state; the 2D map labels the same stops `C1` through `C5`.
- Fixed automatic pause after the final job: the controller now keeps running
  while an unassigned AMR is outside the charging area, so it returns to the
  depot instead of remaining near pickup or delivery.
- The full 40-test Python suite and JavaScript syntax check pass. Browser
  inspection confirmed all five charge labels and pads in the live 3D view.

## Shared depot capacity, fleet growth and decision log

- Extended the measured charging floor to eight non-overlapping, individually
  approached depot slots. The original five AMRs now start on slots 1–5.
- Added an `Add robot` control and API. New AMRs spawn only on a free slot and
  the fleet is capped at eight. Idle and low-battery AMRs choose an available
  slot instead of relying on a fixed robot-number assignment.
- Added dynamic 3D robot copies for AMRs 6–8, and temporary copies in the
  optional Blender live sync. The 3D view has a full screen control.
- Added a visible controller decision log and route-choice messages. Predicted
  robot conflicts identify the other AMR and explain the safety hold/reroute.
- Verified eight browser-visible charge labels, adding AMRs 6–8, the disabled
  ninth-add control, and full screen. All 44 Python tests and JavaScript syntax
  checks pass.
