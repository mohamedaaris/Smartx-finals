"""Mirror executed controller state into the original open warehouse scene.

Run this in Blender after starting app.py. Source assets remain in place except
for the five robot transforms. Runtime graphics use a separate overlay collection.
No blend file is saved. Stop with:
bpy.app.timers.unregister(bpy.app.driver_namespace['vinland_sync'])
"""
import bpy
import gc
import json
import math
import types
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\ASUS\Documents\Smartx Vinland")
STATE_URL = "http://127.0.0.1:8765/api/state"
MANIFEST = json.loads((ROOT / "web/assets/model_manifest.json").read_text())
COLLECTION = "AMR Simulation Overlay"
COLORS = [(0.04,.65,.48,1),(.18,.40,.83,1),(.85,.48,.08,1),(.75,.24,.32,1),(.52,.31,.78,1)]

# Remove previous registered versions, including the earlier connector session.
for function in gc.get_objects():
    if type(function) is types.FunctionType and function.__name__ == "vinland_sync_tick":
        if bpy.app.timers.is_registered(function):
            bpy.app.timers.unregister(function)

collection = bpy.data.collections.get(COLLECTION)
if collection is None:
    collection = bpy.data.collections.new(COLLECTION)
    bpy.context.scene.collection.children.link(collection)
for obj in collection.objects:
    obj.hide_viewport = True
    obj.hide_render = True


def material(name, color):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    principled = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = .65
    return mat


def visible(obj, show=True):
    obj.hide_viewport = not show
    obj.hide_render = not show


def cube(name, dimensions=(.64,.64,.48), color=(.72,.45,.19,1)):
    obj = bpy.data.objects.get(name)
    if obj is None:
        mesh = bpy.data.meshes.new(name)
        x,y,z = [v/2 for v in dimensions]
        mesh.from_pydata([(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                         (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)], [],
                        [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        obj.data.materials.append(material("Vinland " + name.split()[1],color))
        bevel = obj.modifiers.new("Payload edge", "BEVEL")
        bevel.width = .025
        bevel.segments = 2
    visible(obj)
    return obj


def label(name, text, location, color=(.08,.2,.28,1)):
    obj = bpy.data.objects.get(name)
    if obj is None:
        data = bpy.data.curves.new(name,"FONT")
        data.size = .35
        data.extrude = .004
        obj = bpy.data.objects.new(name,data)
        collection.objects.link(obj)
        data.materials.append(material("Vinland Label",color))
    obj.data.body = text
    obj.location = location
    visible(obj)
    return obj


def route(name, points, color):
    obj = bpy.data.objects.get(name)
    if obj is None:
        data = bpy.data.curves.new(name,"CURVE")
        data.dimensions = "3D"
        data.bevel_depth = .035
        data.bevel_resolution = 1
        obj = bpy.data.objects.new(name,data)
        collection.objects.link(obj)
        data.materials.append(material("Vinland " + name,color))
    points = points if len(points)>1 else points+points
    obj.data.splines.clear()
    spline = obj.data.splines.new("POLY")
    spline.points.add(len(points)-1)
    for point, position in zip(spline.points,points):
        point.co = (*position,1)
    visible(obj)
    return obj


last_error = None


def vinland_sync_tick():
    global last_error
    try:
        with urllib.request.urlopen(STATE_URL,timeout=.4) as response:
            state = json.load(response)
        floor = MANIFEST["floor_z"]
        nodes = {n["id"]:n for n in state["geometry"]["nodes"]}
        for name,bounds in state["geometry"]["zones"].items():
            x0,y0,x1,y1 = bounds
            color = {"pickup":(.15,.44,.8,1),"delivery":(.8,.2,.25,1),"charging":(.05,.7,.4,1)}[name]
            route("AMR Zone " + name,[(x0,y0,floor+.06),(x1,y0,floor+.06),(x1,y1,floor+.06),(x0,y1,floor+.06),(x0,y0,floor+.06)],color)
            label("AMR Zone Label " + name,name.upper(),((x0+x1)/2-1,(y0+y1)/2,floor+.1),color)
        for i,item in enumerate(state["robots"]):
            rid = item["id"]
            source = MANIFEST["robots"][rid]
            obj = bpy.data.objects.get(source["source_object"])
            if obj is None:
                raise RuntimeError("Original AMR mesh missing: " + source["source_object"])
            obj.location.x, obj.location.y = item["x"],item["y"]
            obj.location.z = floor + source["position"][2] - source["bounds"][2] + .015
            obj.rotation_euler.z = item["heading"] - math.pi/2
            status = "WAITING" if item["block_reason"] else item["status"].replace("_"," ")
            label("AMR Label " + rid, f"{rid}  {item['battery']:.0f}%\n{status}",
                  (item["x"]-.65,item["y"]+.9,floor+1.3))
            points = [(item["x"],item["y"],floor+.07)] + [(nodes[n]["x"],nodes[n]["y"],floor+.07) for n in item["route"]]
            route("AMR Route " + rid, points, COLORS[i])
            if item["status"] == "CHARGING":
                phase = state["time"]*2
                radius = 1.25+.08*math.sin(phase)
                route("AMR Charging " + rid, [(item["x"]+radius*math.cos(j*math.tau/40),item["y"]+radius*math.sin(j*math.tau/40),floor+.09) for j in range(41)],(.05,.8,.32,1))
            else:
                charging = bpy.data.objects.get("AMR Charging " + rid)
                if charging: visible(charging,False)
        active = set()
        for package in state["packages"]:
            if not package.get("position"):
                continue
            name = "AMR Tracked " + package["id"]
            obj = cube(name)
            obj.location = package["position"]
            obj.data.materials[0] = material("Vinland Packed" if package["stage"] in ("PACKED","CONVEYOR","DELIVERED") else "Vinland Tracked",(.25,.65,.5,1) if package["stage"] in ("PACKED","CONVEYOR","DELIVERED") else (.72,.45,.19,1))
            active.add(name)
        for obj in collection.objects:
            if obj.name.startswith("AMR Tracked ") and obj.name not in active:
                visible(obj,False)
        intake_names = set()
        for i,task in enumerate([t for t in state["tasks"] if t["kind"] == "INBOUND"][:24]):
            name = "AMR Intake " + task["id"]
            obj = cube(name)
            obj.location = (-17.25+i%3*.75,12.9-(i//3)%2*.75,floor+.25+(i//6)*.5)
            intake_names.add(name)
        for obj in collection.objects:
            if obj.name.startswith("AMR Intake ") and obj.name not in intake_names:
                visible(obj,False)
        active_obstacles = set()
        for obstacle in state["obstacles"]:
            name = "AMR Obstacle " + obstacle["id"]
            human = obstacle["category"] == "human"
            obj = cube(name,(.6,.6,1.75 if human else .7),(.86,.25,.08,1))
            obj.location = (obstacle["x"],obstacle["y"],floor+(.875 if human else .35))
            label(name+" Label",obstacle["category"].upper(),(obstacle["x"]-.7,obstacle["y"]+.5,floor+2))
            active_obstacles.update((name,name+" Label"))
        for obj in collection.objects:
            if obj.name.startswith("AMR Obstacle ") and obj.name not in active_obstacles:
                visible(obj,False)
        active_locks = set()
        for kind in ("shelves","conveyors","charging","waiting","junctions"):
            for resource,owner in state["locks"][kind].items():
                n = nodes[resource]
                name = "AMR Lock " + resource
                points = [(n["x"]-1,n["y"]-1.3,floor+.06),(n["x"]+1,n["y"]-1.3,floor+.06),
                          (n["x"]+1,n["y"]+1.3,floor+.06),(n["x"]-1,n["y"]+1.3,floor+.06),
                          (n["x"]-1,n["y"]-1.3,floor+.06)]
                route(name,points,(.95,.57,.12,1))
                active_locks.add(name)
        for obj in collection.objects:
            if obj.name.startswith("AMR Lock ") and obj.name not in active_locks:
                visible(obj,False)
        bpy.app.driver_namespace["vinland_sync_state"] = {"run_id":state["run_id"],"time":state["time"],
             "packages":len(state["packages"]),"robots":len(state["robots"]),"paused":state["paused"]}
        last_error = None
    except Exception as exc:
        message = str(exc)
        if message != last_error:
            print("Vinland sync waiting:",message)
            last_error = message
    return .25


bpy.app.driver_namespace["vinland_sync"] = vinland_sync_tick
bpy.app.timers.register(vinland_sync_tick,first_interval=.1,persistent=True)
print("Vinland original-model sync active: robots, packages, routes, reservations and charging")
