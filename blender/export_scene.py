"""Export a display derivative of the supplied scene; never save the source blend.

Run inside Blender. Static geometry is batched, original robot meshes are reduced
only on temporary copies, and source IDs/measurements are written to a manifest.
"""
import bpy
import json
from pathlib import Path
from mathutils import Vector

ROOT = Path(r"C:\Users\ASUS\Documents\Smartx Vinland")
OUT = ROOT / "web" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
ROBOT_NAMES = ["robot1", "robot2", "robot3", "robot4", "robot2.001"]
WALL_NAMES = {"Line001_08 - Default_0", "Line001_08 - Default b_0"}


def bounds(obj):
    points = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


def export():
    source = bpy.context.scene
    source_window = bpy.context.window
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    objects = [o for o in source.objects if o.type == "MESH" and len(o.data.vertices)
               and not o.name.startswith("AMR ") and not o.hide_get()]
    manifest = {"source": bpy.data.filepath, "source_objects": len(objects),
                "floor_z": bounds(bpy.data.objects["Rectangle001_floor_0"])[5],
                "robots": {}, "slots": {}, "walls": [], "export": "warehouse.glb"}
    for i, name in enumerate(ROBOT_NAMES, 1):
        obj = bpy.data.objects[name]
        manifest["robots"][f"AMR-{i:02d}"] = {"source_object": name, "node": "AMR_ASSET_" + name,
            "position": list(obj.matrix_world.translation), "bounds": bounds(obj), "rotation_z": obj.rotation_euler.z}
    slot_namespace = {"__name__":"vinland_slots"}
    exec(compile((ROOT/"blender/measure_slots.py").read_text(),"measure_slots.py","exec"),slot_namespace)
    manifest.update(slot_namespace["measure_slots"](source))
    temp = bpy.data.scenes.new("AMR Export Temporary")
    mesh_copies = []
    static = []
    try:
        source_window.scene = temp
        for obj in objects:
            clone = obj.copy()
            clone.parent = None
            clone.matrix_world = obj.matrix_world.copy()
            clone.animation_data_clear()
            temp.collection.objects.link(clone)
            clone.hide_viewport = False
            clone.hide_render = False
            clone.hide_set(False)
            if obj.name in ROBOT_NAMES:
                clone.name = "AMR_ASSET_" + obj.name
                clone.data = obj.data.copy()
                mesh_copies.append(clone.data)
                mod = clone.modifiers.new("Display optimization", "DECIMATE")
                mod.ratio = .065
                bpy.context.view_layer.objects.active = clone
                clone.select_set(True)
                bpy.ops.object.modifier_apply(modifier=mod.name)
                clone.select_set(False)
            elif obj.name in WALL_NAMES:
                clone.name = "AMR_WALL_" + str(len(manifest["walls"]))
                manifest["walls"].append({"node": clone.name, "source_object": obj.name})
            else:
                static.append(clone)
        for obj in static:
            obj.select_set(True)
        static[0].data = static[0].data.copy()
        mesh_copies.append(static[0].data)
        bpy.context.view_layer.objects.active = static[0]
        bpy.ops.object.join()
        bpy.context.object.name = "AMR_ORIGINAL_WAREHOUSE"
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.gltf(filepath=str(OUT / "warehouse.glb"), export_format="GLB",
            use_selection=True, export_animations=False, export_cameras=False,
            export_lights=False, export_yup=True, export_apply=True)
        manifest["bytes"] = (OUT / "warehouse.glb").stat().st_size
        (OUT / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("AMR model export complete", manifest["bytes"], "bytes")
    finally:
        source_window.scene = source
        for obj in list(temp.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(temp)
        for mesh in mesh_copies:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        for obj in source.objects:
            obj.select_set(obj in selected)
        bpy.context.view_layer.objects.active = active


export()
