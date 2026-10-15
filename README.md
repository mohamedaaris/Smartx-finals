# Vinland warehouse simulation lab

A capacity-limited AMR controller and operations dashboard built around the supplied
`3d warehouse model/warehouse1.blend`. The browser loads the original warehouse and
robot assets from a Blender export. The connected Blender scene can display the same
controller state. The source blend file is never saved or replaced by the scripts.

## Run

From the project directory in PowerShell:

```powershell
.\run.cmd
```

Or run `python app.py`. Open [http://127.0.0.1:8765](http://127.0.0.1:8765).
Startup is **paused, with no requests or performance history**. The source model's
858 visible cartons are counted as starting stock across the 12 rack rows, so
delivery can be planned immediately.
Five original AMRs start at separate positions in the extended charging depot.
Initial charge defaults to 100% and is explicitly a simulation input. The depot
has eight shared charging slots. **Add robot** places one new AMR in an available
slot, up to eight robots total. Any AMR may use any free slot on return.

On a fresh checkout, install the local rendering dependency once:

```powershell
npm install
```

Python 3.10+ is required; the controller uses only its standard library. Three.js is
served locally, with no CDN dependency. If port 8765 is occupied, stop the existing
project server before starting another one. Windows uses exclusive port binding.

## Assign and run an operator-planned job

The delivery shelf dropdown lists occupied, available slots. Source stock is
available from the `-SRC` shelf groups at startup. If a group is depleted or
reserved, the dropdown explains that no stored package is available.

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
   or unknown object. The sensing toggle draws every AMR's 5 m sensing circle, and
   the monitor lists what the selected robot detects. Clear obstacles in the
   Obstacles tab.
6. Set **New run** initial charge to 20% to exercise charging. Below the 30% charge
   trigger, an active job is suspended and resumed after charging. A robot at 0%
   stops rather than moving. The minimum setup charge remains 15%.
7. The controller pauses after work, charging and parking settle. **Export** saves
   the measured run, events and traces as JSON. Queued jobs can be cancelled.

## Automated order route

Use **Automation** on the existing site, or open
`http://127.0.0.1:8765/automation`. This route reuses the original Blender
warehouse renderer and shows API-driven robot movement, routes, package transfers,
and shelf selection in 3D. Its robots, inventory, orders, and clock are isolated
from the manual route. The controller runs automatically after it receives work.

Edit `automation_catalog.json` before startup to define product shelf groups. The
initial mapping gives the 12 requested products one shelf, two vacant pilot
slots, and the source cartons measured in that shelf. The page shows stock and
assignments for every product. Source boxes have no product labels in Blender;
the catalog defines their product identity by shelf group.

POST an order to `/api/automation/orders` using JSON such as:

```json
{"orderid":"ORD-1001","productname":"TV","ordertime":"2026-10-15T12:30:00+05:30","operation":"STORE","quantity":1}
```

Use `DELIVER` to retrieve stored stock. The optional `productid` must match the
product name. An identical order ID retry is deduplicated; changed data under
the same ID is rejected. GET `/api/automation/orders/{orderid}` or
`/api/automation/state` to check progress. Storage waits when its product shelf
is full; delivery waits when that product has no stock.

The automated route polls `http://192.168.56.1:5000/api/orders` every five seconds
by default. This source only feeds `/automation`; the manual dashboard does not
import its orders. The current company response has an `orders` array with
`orderid`, `product`, and `time`. Each record defaults to `DELIVER` because this
feed does not include an operation. A future record with `operation: "STORE"` or
`"DELIVER"` uses its explicit value. The source can also be changed or polled
immediately in the **Order API source** panel. An identical order ID is imported
only once.

To see the live feed, start the order API service, run `.\run.cmd` from this folder,
and open `http://127.0.0.1:8765/automation`. Let the 3D model finish loading,
then send a new order to the company API or use the test-order form. The 3D view
shows the assigned AMR moving through its operation; click its order row to select
its robot and shelf, then choose **Follow AMR** if desired. The source panel shows
its last poll and any error. **Incoming orders** shows each ID, operation, assigned
robot, shelf slot, and progress. **Product shelf groups** shows remaining stock.
If the server
was already running when this source was configured, restart it to load the new
default. The feed is a read-only GET and must be reachable from the machine running
`app.py`.

The feed may return one order, an array, or `{"orders":[...]}`; an optional bearer
token can be entered in the source panel.
This is still a simulation: source settings, orders and stock are in memory, and
real product dimensions, inbound API authentication and robot hardware control
must be addressed before deployment.

Use **Full screen** above the 3D view for an expanded warehouse view; Escape exits.
The **Controller decision log** shows route choices, assignments, charging stops,
collision holds, reroutes and completions. The full event stream remains available
under the Jobs and inventory records.

Clicking an occupied inventory slot prepares a delivery job for that exact slot.
Selecting a slot in the inventory grid or 2D map now opens a shared slot inspector;
the 3D view also provides shelf-slot pick regions. An available empty slot can prefill
a putaway job, and an occupied slot can prefill a retrieval job. The 24 mapped
vacant pilot slots each hold one simulated 0.64 × 0.64 × 0.48 m package. Another
12 source-stock pick faces represent the original cartons by shelf row. Their
physical weight limits have not been verified.
Setup changes motion, the charge trigger (30–40%), recharge target, packing and
conveyor duration while paused. Legacy single-request and batch API endpoints remain
available for existing integrations; the site uses the manual-job endpoint.

## Data and visual behavior

- No generated completion counts, invented KPI history or default demo requests
  appear at startup. Existing source cartons are initial stock; new pilot stock
  is created only by executed inbound storage.
- Outbound orders for missing stock remain queued. Slot, shelf, conveyor, junction,
  waiting-position and charging locks have actual owners.
- Packages have pickup, storage, retrieval, packing, deposit and delivery timestamps.
  An outbound request cannot complete before its package reaches delivery.
- The inspected blue region contains no existing package stack in the current file.
  Intake display boxes appear only for inbound requests created by the operator. Their
  display stays unchanged during pickup; inventory accounting begins with collected
  and stored package records. At most 24 intake display boxes are shown.
- The Blender export contains 3,304 source box meshes. Grouping their component
  meshes yields **858 cartons**: 81/82/82/41 in rows 1–4 of each rack column.
  Startup stock counts these cartons and exposes one pick face per shelf row;
  retrieval advances that row to its next source carton. The 24 separate pilot
  slots remain vacant for putaway. Calibration inspected 672 boards and found
  294 vacant board centres. The original static source boxes stay visible after
  virtual retrieval in the browser; source inventory movement is simulated.
- Both 3D displays consume the same package transfer positions, robot poses, routes
  and resource state. Camera movement is a viewing control; robot paths come from A*.
- Travel, waiting time, clearance, throughput and battery traces are measured during
  controller steps. Empty charts stay empty. The dashboard samples the full retained
  timeline; exported reports retain up to 3,600 raw samples and 2,000 events.

## Live Blender

Keep the supplied `warehouse1.blend` open and run `blender/live_sync.py` in Blender's
Scripting workspace after the server starts. It moves the existing `robot1`, `robot2`,
`robot3`, `robot4`, and `robot2.001` meshes, creates temporary copies for added
AMRs, aligns their bases to the measured floor,
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
| West, between rack columns A/B | 6.31 m | 4.89 m |
| Middle, between rack columns B/C | 6.66 m | 4.89 m |
| East, rack C to boundary | 4.02 m | 4.89 m |

The two inter-rack straight gaps have enough rack-to-rack width for three nominal
lanes, but turns, fixed equipment and passing have not been validated. The east
gap does not meet the straight-width requirement. The
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

The tests cover prompt scenarios A–L, manual robot/slot/conveyor assignment,
battery interruption/resume, 0% immobilization, sensing, center-first routing,
source-stock startup, real inventory creation,
packing/delivery completion, obstacles between waypoints, five-robot charging congestion,
original model identity, API behavior, oriented corner contact, orphaned reservations,
orders arriving during charging, and automatic pause after the fleet settles.
Source cartons are present in the normal app runtime. Empty warehouse fixtures
remain available to controller unit tests.

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
