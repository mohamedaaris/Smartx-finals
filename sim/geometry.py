"""Measured operational geometry from warehouse1.blend (metres, Blender XY)."""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import dist
import json
from pathlib import Path

FLOOR = (-18.82, -50.57, 10.20, 15.04)
ROBOT_WIDTH = 1.33
ROBOT_LENGTH = 2.01
SIDE_CLEARANCE = 0.15
DETECTION_RADIUS = 5.0
MIN_SEPARATION = 2.35

# Rack meshes and their stock were measured in the source scene. The former
# wider boxes came from end/overhead structures and understated floor clearance.
RACK_X = [(-13.99, -12.08), (-5.77, -3.56), (3.10, 5.02)]
RACK_Y = [(-39.96, -33.76), (-27.07, -20.87), (-14.73, -8.52), (-2.56, 3.65)]
RACKS = [(xa, ya, xb, yb) for xa, xb in RACK_X for ya, yb in RACK_Y]
ZONES = {
    "pickup": (-18.14, 8.02, -10.94, 13.86),
    "delivery": (1.10, 8.02, 9.00, 13.86),
    # Plane.003 in the current Blender scene spans the charging/depot floor.
    "charging": (-18.18, -49.40, 9.01, -43.57),
}
CONVEYORS = [(-10.79, 12.82, -5.02, 13.80), (-4.71, 12.82, 1.06, 13.80)]
# Conservative rack-to-rack gaps across all four shelf rows. The east aisle
# ends at the source scene's inner wall line. Straight width alone does not
# validate operational passing, turns, or station approaches.
AISLES = {"west": (-12.08, -5.77), "middle": (-3.56, 3.10), "east": (5.02, 9.04)}
LANE_CLEARANCES = {
    k: round(b - a - ROBOT_WIDTH - 2 * SIDE_CLEARANCE, 2)
    for k, (a, b) in AISLES.items()
}
THREE_LANE_REQUIRED_WIDTH = round(3 * (ROBOT_WIDTH + 2 * SIDE_CLEARANCE), 2)
THREE_LANE_FEASIBLE = all(b - a >= THREE_LANE_REQUIRED_WIDTH for a, b in AISLES.values())


@dataclass(frozen=True)
class Node:
    id: str
    x: float
    y: float
    kind: str = "travel"


class NavigationGraph:
    """Graph follows the clear aisles and cross aisles visible in the Blender model."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, dict[str, float]] = {}
        manifest = Path(__file__).resolve().parents[1] / "web/assets/model_manifest.json"
        self.model = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        self._build()

    def add(self, name: str, x: float, y: float, kind: str = "travel") -> None:
        self.nodes[name] = Node(name, x, y, kind)
        self.edges[name] = {}

    def connect(self, a: str, b: str, penalty: float = 0) -> None:
        na, nb = self.nodes[a], self.nodes[b]
        weight = dist((na.x, na.y), (nb.x, nb.y)) + penalty
        self.edges[a][b] = self.edges[b][a] = weight

    def _build(self) -> None:
        xs = {"L": -16.70, "A": -8.40, "B": -0.91, "C": 7.05, "R": 8.15}
        ys = {"N": 5.40, "1": -5.25, "2": -17.90, "3": -30.55, "S": -42.20}
        for col, x in xs.items():
            for row, y in ys.items():
                self.add(f"{col}{row}", x, y, "junction" if row in "123" else "travel")
        for col in xs:
            for a, b in zip(ys, list(ys)[1:]):
                self.connect(f"{col}{a}", f"{col}{b}")
        for row in ys:
            for a, b in zip(xs, list(xs)[1:]):
                self.connect(f"{a}{row}", f"{b}{row}")

        # Shelf dock points remain on the one robot-wide aisle. Their protected
        # segments are exclusive because three parallel lanes do not fit.
        shelf_ys = [0.55, -11.62, -23.97, -36.86]
        row_pairs = [("N", "1"), ("1", "2"), ("2", "3"), ("3", "S")]
        for col in "ABC":
            for i, (top, bottom) in enumerate(row_pairs):
                sid = f"{col}R{i + 1}"
                self.add(sid, xs[col], shelf_ys[i], "shelf")
                self.edges[f"{col}{top}"].pop(f"{col}{bottom}")
                self.edges[f"{col}{bottom}"].pop(f"{col}{top}")
                self.connect(f"{col}{top}", sid)
                self.connect(sid, f"{col}{bottom}")

        # These cross aisle positions are clear of rack footprints and leave
        # the longitudinal robot passages unobstructed.
        for name, x, y, a, b in [
            ("WAIT_W", -12.4, -5.25, "L1", "A1"),
            ("WAIT_M", -4.6, -17.90, "A2", "B2"),
            ("WAIT_E", 3.0, -30.55, "B3", "C3"),
        ]:
            self.add(name, x, y, "waiting")
            self.edges[a].pop(b)
            self.edges[b].pop(a)
            self.connect(a, name)
            self.connect(name, b)

        for name, x, y, kind, parent in [
            ("PICKUP", -14.5, 10.25, "pickup", "LN"),
            ("PACKING", -2.7, 10.40, "packing", "BN"),
            ("DELIVERY", 5.25, 10.25, "delivery", "CN"),
            ("CHARGE_1", -15.55, -46.35, "charging", "LS"),
            ("CHARGE_2", -12.90, -46.35, "charging", "LS"),
            ("CHARGE_WAIT", -9.90, -46.35, "waiting", "AS"),
        ]:
            self.add(name, x, y, kind)
            self.connect(name, parent)
        self.add("CHARGE_EXIT_1", -16.00, -49.00, "parking")
        self.add("CHARGE_EXIT_2", -10.00, -49.05, "parking")
        self.connect("CHARGE_1", "CHARGE_EXIT_1")
        self.connect("CHARGE_2", "CHARGE_EXIT_2")
        for i, x in enumerate((-8.0, -3.8, -0.3), 1):
            name = f"CONV_{i}"
            # Conveyor front edge is y=12.82; the AMR front stops just short
            # of it at this measured, footprint-aware transfer approach.
            self.add(name, x, 11.60, "conveyor")
            self.connect(name, "AN" if i == 1 else "BN")
        for name, x, y, parent in [
            ("PARK_A", -11.50, 7.80, "AN"),
            ("PARK_A2", -5.30, 8.10, "AN"),
            ("PARK_B", 3.10, 7.95, "BN"),
            ("PARK_C", 7.05, -45.20, "CS"),
            ("PARK_D", -12.40, -45.30, "LS"),
            ("PARK_E", -4.55, -45.30, "BS"),
        ]:
            self.add(name, x, y, "parking")
            self.connect(name, parent)
        # Eight separated stops fill the extended charging floor. Each has a
        # straight approach from the south aisle and room for one AMR.
        depot_xs = (-16.4, -13.1, -9.8, -6.5, -3.2, 0.1, 3.4, 6.7)
        for a, b in (("LS", "AS"), ("AS", "BS"), ("BS", "CS")):
            self.edges[a].pop(b)
            self.edges[b].pop(a)
        south_chain = ["LS"]
        for i, x in enumerate(depot_xs, 1):
            if i == 4:
                south_chain.append("AS")
            if i == 6:
                south_chain.append("BS")
            entry = f"DEPOT_ENTRY_{i}"
            self.add(entry, x, -42.20)
            south_chain.append(entry)
            self.add(f"DEPOT_{i}", x, -47.80, "depot")
            self.connect(entry, f"DEPOT_{i}")
        south_chain.append("CS")
        for a, b in zip(south_chain, south_chain[1:]):
            self.connect(a, b)
        # The source AMR-03 starts beside bay 2. Its short docking connection
        # avoids an unnecessary trip through the common charging entrance.
        self.connect("PARK_D", "CHARGE_2")
        # Bay 2's diagonal to LS crosses the other bay's protected footprint.
        # Approach through its adjacent source parking point instead.
        self.edges["CHARGE_2"].pop("LS")
        self.edges["LS"].pop("CHARGE_2")

    def nearest(self, x: float, y: float) -> str:
        return min(self.nodes, key=lambda n: dist((x, y), (self.nodes[n].x, self.nodes[n].y)))

    def path(self, start: str, goal: str, blocked: set[str] | None = None,
             charge_route: bool = False, blocked_edges: set[tuple[str, str]] | None = None) -> list[str]:
        blocked = blocked or set()
        if goal in blocked:
            return []
        queue = [(0.0, 0.0, start)]
        best = {start: 0.0}
        prev: dict[str, str] = {}
        while queue:
            _, cost, node = heappop(queue)
            if cost > best.get(node, float("inf")):
                continue
            if node == goal:
                out = [goal]
                while out[-1] != start:
                    out.append(prev[out[-1]])
                return list(reversed(out))
            # Stable order gives deterministic right-side preference where equal.
            for nxt, weight in sorted(self.edges[node].items(), key=lambda p: (-self.nodes[p[0]].x, p[0])):
                if nxt in blocked or tuple(sorted((node, nxt))) in (blocked_edges or set()):
                    continue
                extra = 18.0 if charge_route and nxt[0] in "ABC" and self.nodes[nxt].y > -42.2 else 0.0
                new = cost + weight + extra
                if new + 1e-9 < best.get(nxt, float("inf")):
                    best[nxt], prev[nxt] = new, node
                    h = dist((self.nodes[nxt].x, self.nodes[nxt].y),
                             (self.nodes[goal].x, self.nodes[goal].y))
                    heappush(queue, (new + h, new, nxt))
        return []

    def as_dict(self) -> dict:
        return {"floor": FLOOR, "racks": RACKS, "zones": ZONES,
                "conveyors": CONVEYORS, "aisles": AISLES,
                "lane_clearances": LANE_CLEARANCES,
                "three_lane_required_width": THREE_LANE_REQUIRED_WIDTH,
                "three_lane_feasible": THREE_LANE_FEASIBLE,
                "model": {"source": "warehouse1.blend", "source_meshes": self.model.get("source_objects"),
                          "floor_z": self.model.get("floor_z", 1.825),
                          "slot_validation": self.model.get("slot_validation",{})},
                "nodes": [vars(n) for n in self.nodes.values()],
                "edges": [[a, b] for a, near in self.edges.items() for b in near if a < b]}
