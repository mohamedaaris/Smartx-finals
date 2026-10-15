# AMR simulation redesign

## Objective

Demonstrate the hardware warehouse workflows in software using the supplied
`3d warehouse model/warehouse1.blend`: actual task execution, package pickup,
shelf storage/retrieval, packing, conveyor delivery, traffic coordination,
obstacle response, battery use and charging. Both views share controller state.

## Data contract

- Start paused with no tasks, stock, completed work or invented KPI history.
- Robot initial charge is a configurable simulation input, not a hardware reading.
- User actions create requests. Packages enter logical inventory only after storage.
- Outbound requests wait for stock and locks. Delivery is recorded at conveyor exit.
- Metrics, traces, completion records and history are calculated during execution.
- Scenario fixtures belong to automated validation only and are explicitly marked.
- The physical pickup display remains unchanged, as required by the prompt.

## Implementation sequence — completed

1. Inspect the live Blender scene and export its original asset geometry for the
   browser; retain original object IDs and transforms. Optimize derivative meshes
   for display without changing the source model.
2. Remove default seeded inventory/tasks; add a controlled run lifecycle and
   operator inputs. Capture movement, coordination, task and package traces.
3. Complete packing and conveyor delivery semantics and render every package stage.
4. Build the 3D operations workspace, synchronized 2D map, robot inspection,
   order/inventory panels, resource locks, sensor overlays and measured analytics.
5. Validate workflows from an empty run, model identity, data consistency,
   reservations, obstacle clearance, charging and browser operation.

Completion evidence: 26 passing automated tests, executed browser workflow and
charging reports in `validation/`, and verified live Blender synchronization.
See `PROGRESS.md` for fixes and the remaining physical-validation limits.

## Geometry constraint

Source rack-to-rack straight gaps are conservatively 6.31 / 6.66 / 4.02 m.
Three parallel passages require at least 4.89 m for the current AMR footprint
and clearance. The first two gaps pass only the straight-width check; the east
gap fails. Keep the exclusive-passage controller until the source scene, turns,
passing and station approaches are validated for operational lanes.

## Model policy

Use GPT-6 Sol for incremental implementation and verification. Reserve GPT-6
Astra for unresolved complex bugs, architecture reviews or major source mesh edits.
