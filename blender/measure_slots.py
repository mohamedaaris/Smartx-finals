"""Find vacant source shelf surfaces without moving existing stock or rack assets."""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def bounds(obj):
    points = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


def intersects(position, extent, box):
    return all(min(position[i]+extent[i],box[i+3])-max(position[i]-extent[i],box[i]) > .002 for i in range(3))


def measure_slots(scene):
    boards,boxes,objects = [],[],[]
    for obj in scene.objects:
        if obj.type != "MESH" or not len(obj.data.vertices) or obj.hide_get() or obj.name.startswith(("AMR ","robot")):
            continue
        b = bounds(obj)
        if max(b[i+3]-b[i] for i in range(3)) < 3:
            objects.append((obj,b))
        if "particle board" in obj.name.lower() and b[5] > 2:
            boards.append((obj,b))
        elif obj.name.lower().startswith("box") and max(b[i+3]-b[i] for i in range(3)) < 3:
            boxes.append((obj,b))
    half = [.32,.32,.24]
    free = []
    for obj,b in boards:
        position = [(b[0]+b[3])/2,(b[1]+b[4])/2,b[5]+.26]
        if not any(intersects(position,half,q) for _,q in boxes):
            free.append((obj,position))
    slots,cache = {},{}

    def mesh_clear(position):
        x,y,z = position
        a,b,c = half
        vertices = [(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),
                    (x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)]
        faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        volume = BVHTree.FromPolygons(vertices,faces)
        for obj,b in objects:
            if not intersects(position,half,b):
                continue
            if obj.name not in cache:
                world_vertices = [obj.matrix_world @ v.co for v in obj.data.vertices]
                cache[obj.name] = BVHTree.FromPolygons(world_vertices,[list(p.vertices) for p in obj.data.polygons])
            if volume.overlap(cache[obj.name]):
                return False
        return True

    for col,x0,x1,dock in [("A",-14.48,-9.79,-8.4),("B",-6.99,-2.30,-.91),("C",.48,5.17,7.05)]:
        for row,y0,y1,y in [(1,-2.56,3.65,.55),(2,-14.73,-8.52,-11.62),(3,-27.07,-20.87,-23.97),(4,-39.96,-33.76,-36.86)]:
            candidates = [(obj,p) for obj,p in free if x0 < p[0] < x1 and y0 < p[1] < y1]
            candidates.sort(key=lambda item: abs(item[1][0]-dock)+abs(item[1][1]-y)+.15*item[1][2])
            chosen = []
            for obj,position in candidates:
                if any(sum((position[k]-q[k])**2 for k in range(3)) < .5 for q in chosen):
                    continue
                if not mesh_clear(position):
                    continue
                chosen.append(position)
                slots[f"{col}R{row}-{len(chosen)}"] = {"position":position,"source_board":obj.name,"validated_vacant":True}
                if len(chosen) == 2:
                    break
            if len(chosen) < 2:
                raise RuntimeError(f"Only {len(chosen)} verified vacant surfaces at {col}R{row}; revise physical capacity before running")
    return {"slots":slots,"slot_validation":{"package_dimensions":[.64,.64,.48],
        "source_boards":len(boards),"vacant_board_centres":len(free),"assigned_slots":len(slots),
        "occupied_source_box_meshes":len(boxes),"method":"Source box bounds and exact neighboring mesh BVH surface checks"}}
