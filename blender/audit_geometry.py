"""Read-only measurement of the open warehouse1.blend source scene.

Run in Blender's Python console or through the Blender MCP code tool:
exec(open(r'<project>/blender/audit_geometry.py', encoding='utf-8').read())
"""

import bpy
import json
from pathlib import Path
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path(bpy.data.filepath).resolve().parents[1]
OUTPUT = ROOT / "validation/source-geometry.json"


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


def aggregate(items):
    boxes = [bounds(obj) for obj in items]
    return [min(b[i] for b in boxes) for i in range(3)] + [max(b[i + 3] for b in boxes) for i in range(3)]


def measure():
    scene = bpy.context.scene
    if Path(bpy.data.filepath).name != "warehouse1.blend":
        raise RuntimeError("Open warehouse1.blend before measuring")
    floor = scene.objects["Rectangle001_floor_0"]
    xbands = [(-14.48, -9.79), (-6.99, -2.30), (0.48, 5.17)]
    ybands = [(3.65, -2.56), (-8.52, -14.73), (-20.87, -27.07), (-33.76, -39.96)]
    racks = {}
    for col, (xa, xb) in zip("ABC", xbands):
        for row, (top, bottom) in enumerate(ybands, 1):
            matches = []
            for obj in scene.objects:
                if obj.type != "MESH" or not obj.name.startswith("shelving") or obj.hide_get():
                    continue
                b = bounds(obj)
                cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
                if xa - 1 < cx < xb + 1 and bottom - 1 < cy < top + 1:
                    matches.append(obj)
            racks[f"{col}R{row}"] = {"bounds": aggregate(matches), "mesh_count": len(matches)}
    robots = {name: {"bounds": bounds(scene.objects[name]),
                     "location": list(scene.objects[name].matrix_world.translation),
                     "scale": list(scene.objects[name].scale),
                     "parent": scene.objects[name].parent.name if scene.objects[name].parent else None}
              for name in ("robot1", "robot2", "robot3", "robot4", "robot2.001")}
    return {"source": bpy.data.filepath, "unit_system": scene.unit_settings.system,
            "unit_scale": scene.unit_settings.scale_length,
            "floor_bounds": bounds(floor), "robots": robots, "racks": racks,
            "note": "Rack bounds include named shelving meshes; nearby stock, walls, floor markings and full swept paths require separate collision checks."}


data = measure()
OUTPUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Wrote {OUTPUT} ({len(data['racks'])} rack groups, {len(data['robots'])} robots)")
