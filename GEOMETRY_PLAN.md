# Candidate three-lane geometry change

Prepared before any source object movement, 2026-10-15.

## Source measurements

`blender/audit_geometry.py` measured the open `warehouse1.blend` and wrote `validation/source-geometry.json`. The scene uses metric units at scale 1.0. The five source robot meshes are approximately 1.327 × 2.012 × 0.601 m. They have no mesh children or non-unit scale. The `web/assets/model_manifest.json` export uses matching size but currently stores different robot poses; the open source scene includes an inactive `AMR Simulation Overlay` collection with 78 objects. That overlay must not be treated as warehouse structure.

The rack mesh gaps are 6.31–6.61 m between A/B and 6.68–6.96 m between B/C. The C-to-east-boundary straight gap is about 4.02 m. The nominal three-lane minimum is 4.89 m, based on three 1.33 m robots with 0.15 m side clearance per lane. This is a straight width requirement, not a passing or turning proof.

## Proposed minimal source edit

Translate the four C-column shelf assemblies `shelving00`, `shelving403`, `shelving806`, and `shelving1209` 0.90 m west (Blender X = −0.90 m). Move the stock objects physically carried by those rack assemblies by the same transform, preserving their parent relationships and relative shelf positions. Inspect whether the long `Box001_08 - Default_0` end/overhead structure is attached to this column; its bounding box alone does not prove a robot-height obstruction, so decide from actual polygons and supports before moving it. Keep the original file recoverable and save a new source variant until all checks pass.

This shift yields a predicted minimum B/C rack gap of about 5.76 m and a predicted C/east gap of about 4.92 m. Both exceed 4.89 m by only 0.87 m and 0.03 m respectively. The east margin is too small to treat as approved: wall protrusions, rack tolerances, robot protrusions, and any added lane separation could erase it. A final translation may need to be larger, which would reduce the B/C margin. The feasible translation interval based on rack bounds alone is approximately 0.87–1.77 m. The final value must come from full collision checks, not this estimate.

## Required preflight before applying the edit

1. Identify the complete object hierarchy for each C rack and every source stock object on it; avoid moving only visible meshes or moving a child twice.
2. Measure fixed equipment, walls, end structures, and their polygon geometry at the full robot and payload height along all shelf rows, cross aisles, junctions, and station approaches.
3. Choose lane centres and check oriented robot footprints and swept turns with 0.15 m side clearance at every y position, including cross aisle entry/exit and waiting points. Include braking and speed assumptions.
4. Confirm that pickup, packing, conveyors, delivery, charging, and the outer boundary route remain connected without rack or stock intersection.
5. Update navigation nodes, lane reservations, shelf docks, 2D geometry, all 24 slot coordinates, and the exported model from the same edited source scene. Preserve existing slot IDs or provide a migration.
6. Generate before/after validation reports and run the fleet and browser tests. Claim three-lane operation only after all physical and traffic tests pass.

Until then, the existing reservation-based single-passage controller is the safe operational behavior.
