# Vinland warehouse simulation lab

A functioning five-AMR controller and operations dashboard built around the supplied
`3d warehouse model/warehouse1.blend`. The browser loads the original warehouse and
robot assets from a Blender export. The connected Blender scene can display the same
controller state. The source blend file is never saved or replaced by the scripts.

## Run

From the project directory in PowerShell:

```powershell
.\run.cmd
```

Or run `python app.py`. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
Startup is **paused, with no requests, tracked stock or performance history**.
The five robot poses are configured from the supplied model; initial charge defaults
to 100% and is explicitly a simulation input.

On a fresh checkout, install the local rendering dependency once:

```powershell
npm install
```

Python 3.10+ is required; the controller uses only its standard library. Three.js is
served locally, with no CDN dependency. If port 8765 is occupied, stop the existing
project server before starting another one. Windows uses exclusive port binding.

## Assign and run an operator-planned job

1. In **Assign a job to an AMR**, choose **Store a new package**, **Deliver a stored
   package**, or **Move robot only**. The available-AMR dropdown shows current status
   and battery. Busy robots and robots at or below the 30% charge trigger cannot be
   assigned a new job.
2. Choose the AMR and exact destination. Storage requires a package SKU and an empty
   shelf slot; its source is PICKUP. Delivery requires an occupied slot and a chosen
   conveyor lane; the robot goes from that shelf through PACKING to the conveyor,
   and the package continues to DELIVERY. Move-only jobs let the operator select a
   station or shelf without transferring a package. The current robot position and
   planned stops appear before submission.
3. Click **Assign this job**, then **Start run** if paused. The controller reserves
   resources and follows the operator's robot, shelf and conveyor choices. It does
   not silently substitute another robot or shelf. Select 1× for observation or a
   faster simulation clock.
4. Watch 3D and 2D routes, the Requests stage strip, and the Traffic and conflict
   monitor. Shelf routes use the center B aisle first and branch through the row
   cross aisle to A or C. Obstructions may require a safe detour. Reservations,
   waits, yields and reroutes are visible with explanations.
5. Use **Place obstacle** in 2D to add an operator-specified human, debris, equipment
   or unknown object. The sensing toggle draws all five 5 m sensing circles, and
   the monitor lists what the selected robot detects. Clear obstacles in the
   Obstacles tab.
6. Set **New run** initial charge to 20% to exercise charging. Below the 30% charge
   trigger, an active job is suspended and resumed after charging. A robot at 0%
   stops rather than moving. The minimum setup charge remains 15%.
7. The controller pauses after work, charging and parking settle. **Export** saves
   the measured run, events and traces as JSON. Queued jobs can be cancelled.

Clicking an occupied inventory slot prepares a delivery job for that exact slot.
Setup changes motion, the charge trigger (30–40%), recharge target, packing and
conveyor duration while paused. Legacy single-request and batch API endpoints remain
available for existing integrations; the site uses the manual-job endpoint.

## Data and visual behavior

- No preloaded SKUs, generated completion counts, invented KPI history or default demo
  requests appear in normal startup. Stock is created by executed inbound storage.
- Outbound orders for missing stock remain queued. Slot, shelf, conveyor, junction,
  waiting-position and charging locks have actual owners.
- Packages have pickup, storage, retrieval, packing, deposit and delivery timestamps.
  An outbound request cannot complete before its package reaches delivery.
- The inspected blue region contains no existing package stack in the current file.
  Intake display boxes appear only for inbound requests created by the operator. Their
  display stays unchanged during pickup; inventory accounting begins with collected
  and stored package records. At most 24 intake display boxes are shown.
- Original boxes on the model's racks remain reference assets. The tracked pilot
  inventory uses **24 logical slots**, each mapped to a verified vacant shelf surface.
  Calibration inspected 672 boards and found 294 vacant board centres; it checks
  source carton bounds and neighboring mesh surfaces without relocating original stock.
- Both 3D displays consume the same package transfer positions, robot poses, routes
  and resource state. Camera movement is a viewing control; robot paths come from A*.
- Travel, waiting time, clearance, throughput and battery traces are measured during
  controller steps. Empty charts stay empty. The dashboard samples the full retained
  timeline; exported reports retain up to 3,600 raw samples and 2,000 events.

## Live Blender

Keep the supplied `warehouse1.blend` open and run `blender/live_sync.py` in Blender's
Scripting workspace after the server starts. It moves the existing `robot1`, `robot2`,
`robot3`, `robot4`, and `robot2.001` meshes, aligns their bases to the measured floor,
and places runtime graphics in **AMR Simulation Overlay**. It shows package transfers,
conveyor motion, routes, lock outlines, station labels, obstacles and charging rings.
Re-running the script replaces its previous timer.

Stop synchronization in Blender's Python console:

```python
bpy.app.timers.unregister(bpy.app.driver_namespace['vinland_sync'])
```

`blender/export_scene.py` creates the browser display derivative. It respects hidden
objects, batches static geometry, keeps the original robot identities and optimizes
temporary robot copies. The source file is not written. After source layout changes,
remeasure navigation geometry before re-exporting or running the controller.

## Measured geometry and limits

The floor spans approximately `x=-18.82..10.20 m`, `y=-50.57..15.04 m`; its upper
surface is at `z=1.825 m`. The AMR footprint is about `1.33 × 2.01 m`.

| Aisle | Usable width | Width needed for three passages |
| --- | ---: | ---: |
| West | 2.80 m | 4.89 m |
| Middle | 2.78 m | 4.89 m |
| East | 3.87 m | 4.89 m |

The source geometry does not support three robots abreast inside one aisle. The
operator-requested center-first policy uses aisle B as the main travel corridor and
branches to shelf aisles A and C at the corresponding cross aisle. Each aisle remains
a protected single passage, with junction/waiting reservations and measured boundary
charging routes. The right boundary is restricted to charging traffic. Charging
entrances are coordinated, bay 2 avoids crossing bay 1, and parking stays outside
the charging region.

The simulation uses geometric safety checks, including oriented robot footprints,
rather than a rigid-body dynamics engine.
Shelf/packing/conveyor transfers are state-driven visual operations; the supplied AMRs
have no articulated gripper rig. Obstacle categories are operator inputs, not camera
AI predictions or physical LiDAR readings. Conservative forecourt admission restricts
simultaneous station movements. Arbitrary long workloads and changed layouts need
additional stress and swept-footprint validation before production use.

The full-detail browser export is about 122 MB. Initial loading and frame rate depend
on local disk and GPU capacity. Walls can be enabled; the cutaway view follows the
source file's hidden roof setting.

## Modules and validation

| File | Responsibility |
| --- | --- |
| `sim/geometry.py` | Measured navigation graph, physical connections and A* |
| `sim/models.py` | Structured robots, slots and requests |
| `sim/inventory.py` | Slot construction and stock/resource eligibility |
| `sim/battery.py` | Route-based energy feasibility and return reserve |
| `sim/sensors.py` | Geometric node and edge obstruction checks |
| `sim/engine.py` | Fleet state machine, traffic coordination and operation transitions |
| `sim/telemetry.py` | Executed measurements and sampled traces |
| `app.py` | Locked controller runtime, run lifecycle and local API |
| `web/scene.js` | Original model loading and 3D state presentation |
| `blender/live_sync.py` | Original scene synchronization |

```powershell
python -m unittest discover -s tests -v
npm run check
```

The **34 tests** cover prompt scenarios A–L, manual robot/slot/conveyor assignment,
battery interruption/resume, 0% immobilization, sensing, center-first routing,
empty startup, real inventory creation,
packing/delivery completion, obstacles between waypoints, five-robot charging congestion,
original model identity, API behavior, oriented corner contact, orphaned reservations,
orders arriving during charging, and automatic pause after the fleet settles.
Seeded fixtures are confined to explicitly selected automated validation scenarios.

Executed browser runs are saved in `validation/workflow-run.json` and
`validation/charging-run.json`. Continuation decisions and validation are in
[PROGRESS.md](PROGRESS.md) and [REDESIGN.md](REDESIGN.md).

To reproduce these explicit live validations against a running lab:

```powershell
python scripts/validate_live.py workflow
python scripts/validate_live.py charging
```

Each command resets the lab, executes its operations, waits for automatic pause and
saves measured data. It refuses to reset a run containing non-validation operator SKUs.

The supplied asset metadata credits **Warehouse by Giimann**. Its original metadata and
imported assets remain in `3d warehouse model/`.

Model preference: GPT-6 Sol for incremental development, tests, debugging and routine UI.
Reserve GPT-6 Astra for unresolved complex bugs, architecture reviews and major source
3D mesh or layout changes.
