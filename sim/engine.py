"""Deterministic five-AMR warehouse simulation and inventory controller."""

from __future__ import annotations

from math import atan2, dist
from typing import Any
from uuid import uuid4

from .telemetry import Telemetry
from .models import Slot, Task, Robot
from .inventory import create_slots, eligible_slots
from .battery import estimate_task_energy
from .sensors import obstructed_nodes, obstructed_edges, footprints_overlap

from .geometry import (DETECTION_RADIUS, MIN_SEPARATION, ZONES, NavigationGraph,
                       ROBOT_LENGTH, ROBOT_WIDTH)

SPEED = 2.5                 # metres per simulation second
TICK = 0.1
BATTERY_TRIGGER = 30.0
RECHARGE_TARGET = 85.0
CRITICAL_BATTERY = 10.0
ENERGY_PER_METRE = 0.11
ENERGY_RESERVE = 5.0
CHARGE_RATE = 1.6            # percentage points per simulation second
JUNCTION_RADIUS = 3.4         # acquire before entering the shared conflict area


class Warehouse:
    def __init__(self, demo: bool = False, fixture: bool = False, initial_battery: float = 100):
        self.graph = NavigationGraph()
        self.time = 0.0
        self.run_id = str(uuid4())
        self.telemetry = Telemetry()
        self.packages: dict[str, dict] = {}
        self.config = {"max_speed": SPEED, "charge_trigger": BATTERY_TRIGGER,
                       "initial_battery": initial_battery,
                       "recharge_target": RECHARGE_TARGET, "conveyor_seconds": 18.0,
                       "operation_seconds": 2.0, "packing_seconds": 3.0}
        self.sequence = 0
        self.package_sequence = 0
        self.obstacle_sequence = 0
        self.events: list[dict[str, Any]] = []
        self.tasks: dict[str, Task] = {}
        self.slots: dict[str, Slot] = {}
        self.shelf_locks: dict[str, str] = {}
        self.conveyor_locks: dict[str, str] = {}
        self.charge_locks: dict[str, str] = {}
        self.edge_locks: dict[tuple[str, str], str] = {}
        self.junction_locks: dict[str, str] = {}
        self.waiting_locks: dict[str, str] = {}
        self.top_owner: str | None = None
        self.charge_owner: str | None = None
        self.obstacles: dict[str, dict] = {}
        self.conveyor_packages: list[dict] = []
        self.robots: dict[str, Robot] = {}
        starts = [
            ("AMR-01", "robot1", "PARK_A2", initial_battery),
            ("AMR-02", "robot2", "PARK_A", initial_battery),
            ("AMR-03", "robot3", "PARK_D", initial_battery),
            ("AMR-04", "robot4", "PARK_E", initial_battery),
            ("AMR-05", "robot2.001", "PARK_B", initial_battery),
        ]
        for rid, source, node, battery in starts:
            p = self.graph.nodes[node]
            self.robots[rid] = Robot(rid, source, node, p.x, p.y, battery)
        self.slots = create_slots(self.graph)
        # Explicit fixtures are for automated scenario tests, never normal startup.
        if fixture or demo:
            for i, sid in enumerate(list(self.slots)[::2], 1):
                self.slots[sid].sku = f"SKU-{i:02d}"
                self.slots[sid].package_id = f"STOCK-{i:03d}"
                self.packages[f"STOCK-{i:03d}"] = {"id": f"STOCK-{i:03d}", "sku": f"SKU-{i:02d}", "stage": "STORED", "slot": sid, "fixture": True}
        if demo or fixture:
            # Retain the original controlled test arrangement for regression tests.
            for r, node, battery in zip(self.robots.values(), ["AR1", "BR2", "L2", "C3", "AR2"], [91,85,76,70,62]):
                p = self.graph.nodes[node]
                r.node, r.x, r.y, r.battery = node, p.x, p.y, battery
        self.log("Simulation ready: five existing AMRs and measured warehouse layout")
        if demo:
            self.request_inbound("SKU-NEW-1")
            self.request_inbound("SKU-NEW-2")
            self.request_outbound("SKU-01")
            self.request_outbound("SKU-05")
            self.request_outbound("SKU-09")
            self.request_outbound("SKU-10")

    def log(self, message: str, level: str = "info") -> None:
        self.events.append({"time": round(self.time, 1), "message": message, "level": level})
        self.events = self.events[-2000:]

    def _new_task(self, kind: str, sku: str) -> Task:
        self.sequence += 1
        task = Task(f"TASK-{self.sequence:04d}", kind, sku.strip(), round(self.time, 3))
        self.tasks[task.id] = task
        self.log(f"{task.id} queued: {kind.lower()} {sku}")
        return task

    def request_inbound(self, sku: str) -> str:
        return self._new_task("INBOUND", sku).id

    def request_outbound(self, sku: str) -> str:
        return self._new_task("OUTBOUND", sku).id

    def request_manual(self, kind: str, robot_id: str, slot_id: str | None = None,
                       sku: str = "", conveyor: str | None = None,
                       destination: str | None = None) -> str:
        """Create one operator-specified route; reject stale UI choices atomically."""
        robot = self.robots.get(robot_id)
        if robot is None:
            raise ValueError("Select an existing AMR")
        if not self._available_for_job(robot) or robot.task_id or any(
                t.state == "QUEUED" and t.requested_robot == robot_id for t in self.tasks.values()):
            raise ValueError(f"{robot_id} is not available; choose an idle or depot-bound AMR")
        if robot.battery <= self.config["charge_trigger"]:
            raise ValueError(f"{robot_id} must charge before accepting a job")
        if kind == "MOVE":
            allowed = {"PICKUP", "PACKING", "DELIVERY"} | {s.shelf for s in self.slots.values()}
            if destination not in allowed:
                raise ValueError("Select a valid station or shelf destination")
            if destination in self.shelf_locks:
                raise ValueError("That shelf is reserved by another job")
            task = self._new_task(kind, destination)
            task.destination = destination
        elif kind in ("INBOUND", "OUTBOUND"):
            slot = self.slots.get(slot_id or "")
            if slot is None:
                raise ValueError("Select a shelf slot")
            if slot.reserved_by or slot.shelf in self.shelf_locks or any(
                    t.state == "QUEUED" and t.requested_slot == slot.id for t in self.tasks.values()):
                raise ValueError(f"{slot.id} is reserved by another job")
            if kind == "INBOUND":
                sku = sku.strip()
                if not 1 <= len(sku) <= 40:
                    raise ValueError("Enter a package SKU of 1–40 characters")
                if not slot.validated_vacant or not slot.position:
                    raise ValueError(f"{slot.id} has not been validated for package placement")
                if slot.sku:
                    raise ValueError(f"{slot.id} already contains {slot.sku}")
            else:
                if not slot.sku:
                    raise ValueError(f"{slot.id} has no package to deliver")
                if conveyor not in ("CONV_1", "CONV_2", "CONV_3"):
                    raise ValueError("Select conveyor lane 1, 2, or 3")
                sku = slot.sku
            task = self._new_task(kind, sku)
            task.requested_slot = slot.id
            task.requested_conveyor = conveyor if kind == "OUTBOUND" else None
        else:
            raise ValueError("Choose Store, Deliver, or Move")
        task.requested_robot = robot_id
        self.log(f"Operator planned {task.id}: {robot_id} from {robot.node} to "
                 f"{task.destination or task.requested_slot}"
                 f"{f' via {task.requested_conveyor}' if task.requested_conveyor else ''}")
        return task.id

    def add_obstacle(self, x: float, y: float, category: str = "unknown") -> str:
        self.obstacle_sequence += 1
        oid = f"OBS-{self.obstacle_sequence:03d}"
        self.obstacles[oid] = {"id": oid, "x": x, "y": y, "category": category}
        self.log(f"{category} obstacle {oid} reported at ({x:.1f}, {y:.1f})", "warning")
        return oid

    def remove_obstacle(self, oid: str) -> None:
        if oid in self.obstacles:
            del self.obstacles[oid]
            self.log(f"Obstacle {oid} cleared")

    def _priority(self, robot: Robot) -> tuple:
        task = self.tasks.get(robot.task_id or "")
        return (0 if robot.battery <= CRITICAL_BATTERY else 1,
                0 if robot.carrying else 1,
                task.assigned if task and task.assigned is not None else float("inf"),
                robot.id)

    def _energy_needed(self, robot: Robot, task: Task, slot: Slot) -> float:
        return (estimate_task_energy(self.graph, robot, task, slot.shelf, ENERGY_PER_METRE,
                                     self.config["charge_trigger"], task.requested_conveyor)
                + dist((robot.x, robot.y), (self.graph.nodes[robot.node].x,
                                             self.graph.nodes[robot.node].y)) * ENERGY_PER_METRE)

    @staticmethod
    def _available_for_job(robot: Robot) -> bool:
        return (robot.status in ("IDLE", "MOVING_TO_DEPOT")
                or (robot.status == "MOVING_FROM_CHARGER" and robot.charge_bay is None))

    @staticmethod
    def _in_charging_area(robot: Robot) -> bool:
        x0, y0, x1, y1 = ZONES["charging"]
        return x0 <= robot.x <= x1 and y0 <= robot.y <= y1

    def _docked(self, robot: Robot) -> bool:
        return (self._in_charging_area(robot) and not robot.edge
                and (robot.status == "CHARGING" or
                     (robot.status == "IDLE" and not robot.task_id))
                and robot.route_index >= len(robot.path))

    def _actively_charging(self, robot: Robot) -> bool:
        return (self._in_charging_area(robot) and robot.battery < 100
                and (robot.status == "CHARGING" or self._docked(robot)))

    def _safe_current_dock(self, robot: Robot) -> bool:
        if not self._docked(robot):
            return False
        # Keep an arbitrary resting point only when it does not obstruct one
        # of the five straight docking approaches or another AMR's footprint.
        for i in range(1, 6):
            entry = self.graph.nodes[f"DEPOT_ENTRY_{i}"]
            dock = self.graph.nodes[f"DEPOT_{i}"]
            nearest_y = max(dock.y, min(entry.y, robot.y))
            if dist((robot.x, robot.y), (dock.x, nearest_y)) < MIN_SEPARATION:
                return False
        return all(other.id == robot.id or
                   dist((robot.x, robot.y), (other.x, other.y)) >= MIN_SEPARATION
                   for other in self.robots.values())

    def _choose_robot(self, task: Task, slot: Slot) -> Robot | None:
        eligible = [r for r in self.robots.values()
                    if self._available_for_job(r) and r.battery > self.config["charge_trigger"]
                    and (r.status == "MOVING_TO_DEPOT" or r.battery >= self._energy_needed(r, task, slot))
                    and not any(t.state == "QUEUED" and t.requested_robot == r.id for t in self.tasks.values())]
        if not eligible:
            return None
        destination = "PICKUP" if task.kind == "INBOUND" else slot.shelf
        p = self.graph.nodes[destination]
        # Initial roles are soft preferences. Any capable idle AMR is eligible.
        def rank(r: Robot):
            preference = 0 if ((task.kind == "INBOUND" and r.id in ("AMR-01", "AMR-02"))
                               or (task.kind == "OUTBOUND" and r.id not in ("AMR-01", "AMR-02"))) else 4
            return (preference + dist((r.x, r.y), (p.x, p.y)) / 10, r.id)
        return min(eligible, key=rank)

    def _queue_assignments(self) -> None:
        # Existing queue is considered in creation order before new work.
        for task in sorted(self.tasks.values(), key=lambda t: (t.created, t.id)):
            if task.state != "QUEUED":
                continue
            if task.kind == "MOVE":
                robot = self.robots[task.requested_robot]
                path = self.graph.path(robot.node, task.destination)
                charge_path = self.graph.path(task.destination, f"DEPOT_{int(robot.id[-2:])}", charge_route=True)
                needed = (sum(self.graph.edges[a][b] for a,b in zip(path,path[1:]))
                          + sum(self.graph.edges[a][b] for a,b in zip(charge_path,charge_path[1:]))) * ENERGY_PER_METRE + self.config["charge_trigger"]
                needed += dist((robot.x, robot.y), (self.graph.nodes[robot.node].x,
                                               self.graph.nodes[robot.node].y)) * ENERGY_PER_METRE
                if (not self._available_for_job(robot) or robot.task_id
                        or (robot.status != "MOVING_TO_DEPOT" and robot.battery < needed)
                        or robot.battery <= self.config["charge_trigger"] or not path or not charge_path):
                    task.reason = "Selected AMR unavailable, route blocked, or battery reserve insufficient"
                    continue
                task.robot, task.assigned, task.state, task.reason = robot.id, round(self.time, 3), "ASSIGNED", ""
                robot.task_id, robot.status = task.id, "MOVING_TO_DESTINATION"
                self._route(robot, task.destination)
                self.log(f"{task.id} assigned to {robot.id}: move from {robot.node} to {task.destination}")
                continue
            candidates, reason = eligible_slots(task,self.slots,self.shelf_locks)
            if task.requested_slot:
                candidates = [s for s in candidates if s.id == task.requested_slot]
                if not candidates:
                    task.reason = f"Selected slot {task.requested_slot} is no longer available"
                    continue
            if not candidates:
                task.reason = reason
                continue
            selection = next(((s, r) for s in candidates
                              if (r := (self.robots.get(task.requested_robot) if task.requested_robot else self._choose_robot(task, s))) is not None
                              and self._available_for_job(r) and r.battery > self.config["charge_trigger"]
                              and (r.status == "MOVING_TO_DEPOT" or r.battery >= self._energy_needed(r, task, s))), None)
            if selection is None:
                task.reason = "Waiting for an eligible robot or battery reserve"
                continue
            slot, robot = selection
            self.shelf_locks[slot.shelf] = task.id
            slot.reserved_by = task.id
            task.slot, task.robot, task.assigned = slot.id, robot.id, round(self.time, 3)
            task.state, task.reason = "ASSIGNED", ""
            robot.task_id = task.id
            robot.status = "MOVING_TO_PICKUP" if task.kind == "INBOUND" else "MOVING_TO_RETRIEVAL"
            self._route(robot, "PICKUP" if task.kind == "INBOUND" else slot.shelf)
            self.log(f"{task.id} assigned to {robot.id}; locked {slot.shelf}")

    def _obstructed_nodes(self) -> set[str]:
        return obstructed_nodes(self.graph,self.obstacles)

    def _obstructed_edges(self) -> set[tuple[str, str]]:
        return obstructed_edges(self.graph,self.obstacles)

    def _route(self, robot: Robot, target: str, avoid: set[str] | None = None) -> bool:
        robot.target = target
        if robot.edge:
            origin = self.graph.nodes[robot.node]
            if dist((robot.x,robot.y),(origin.x,origin.y)) > 1e-6:
                robot.pending_target = target
                robot.pending_avoid = set(avoid or ())
                robot.yield_junction = None
                robot.block_reason = "Clearing current segment before reroute"
                return True
            self.edge_locks.pop(robot.edge,None)
            robot.edge = None
        blocked = self._obstructed_nodes() | (avoid or set())
        blocked |= {shelf for shelf, owner in self.shelf_locks.items()
                    if owner != robot.task_id}
        if robot.status in ("MOVING_TO_CHARGER", "MOVING_TO_CHARGE_WAIT", "MOVING_FROM_CHARGER"):
            blocked |= {n for n, p in self.graph.nodes.items() if p.kind == "shelf"}
        elif robot.status in ("MOVING_TO_PARK", "MOVING_TO_DEPOT"):
            blocked |= set(self.shelf_locks)
        if robot.status not in ("MOVING_TO_CHARGER", "MOVING_TO_CHARGE_WAIT", "MOVING_FROM_CHARGER"):
            # The right boundary is a charging route, not a second parallel
            # passage for normal travel in the constrained east shelf aisle.
            blocked |= {n for n in self.graph.nodes if n.startswith("R")}
        blocked.discard(robot.node)
        charge_route = robot.status in ("MOVING_TO_CHARGER", "MOVING_TO_CHARGE_WAIT", "MOVING_FROM_CHARGER")
        obstructed_edges = self._obstructed_edges()
        path = []
        if (target in {s.shelf for s in self.slots.values()}
                and robot.status in ("MOVING_TO_SHELF", "MOVING_TO_RETRIEVAL", "MOVING_TO_DESTINATION")):
            # Enter the central B aisle first, run to the shelf row, then branch
            # through a cross aisle. If that route is obstructed, use a safe detour.
            entrance = robot.node if robot.node.startswith("B") else ("BN" if robot.y >= -19 else "BS")
            row = int(target[-1])
            gate = target if target.startswith("B") else ("B1", "B2", "B3", "BS")[row - 1]
            first = self.graph.path(robot.node, entrance, blocked, blocked_edges=obstructed_edges)
            center_only = {n for n in self.graph.nodes if not n.startswith("B")}
            middle = self.graph.path(entrance, gate, blocked | center_only,
                                     blocked_edges=obstructed_edges)
            last = self.graph.path(gate, target, blocked, blocked_edges=obstructed_edges)
            if first and middle and last:
                path = first + middle[1:] + last[1:]
        if not path:
            path = self.graph.path(robot.node, target, blocked,
                                   charge_route=charge_route, blocked_edges=obstructed_edges)
        if not path:
            robot.block_reason = f"No safe route to {target}"
            return False
        robot.target, robot.path, robot.route_index = target, path, 1
        self._clear_wait(robot)
        return True

    @staticmethod
    def _edge_key(a: str, b: str) -> tuple[str, str]:
        return tuple(sorted((a, b)))

    def _set_wait(self, robot: Robot, reason: str) -> None:
        if not robot.block_reason:
            robot.blocked_since = self.time
        if reason != robot.block_reason and (reason != robot.last_conflict_reason or self.time - robot.last_conflict_log >= 15):
            self.log(f"Conflict: {robot.id} paused — {reason}; controller is holding or rerouting safely", "warning")
            robot.last_conflict_log = self.time
            robot.last_conflict_reason = reason
        robot.block_reason = reason
        # Movement phase remains intact so the robot resumes it safely.

    def _clear_wait(self, robot: Robot) -> None:
        if robot.block_reason and self.time - robot.blocked_since >= 1 and self.time - robot.last_conflict_log >= 1:
            self.log(f"Conflict resolved: {robot.id} resumed after {robot.block_reason}")
            robot.last_conflict_log = self.time
        robot.block_reason = ""

    def _power_available(self, robot: Robot) -> bool:
        if robot.battery > 0:
            return True
        robot.velocity = 0
        if robot.status != "POWER_DEPLETED":
            robot.status = "POWER_DEPLETED"
            if robot.task_id:
                task = self.tasks[robot.task_id]
                task.state, task.reason = "FAILED", "AMR battery depleted; movement stopped"
            self.log(f"{robot.id} stopped at 0% battery; operator action required", "error")
        return False

    def _spend_power(self, robot: Robot, amount: float) -> bool:
        if robot.battery <= amount:
            robot.battery = 0
            self._power_available(robot)
            return False
        robot.battery -= amount
        return True

    def _move(self, robot: Robot, dt: float) -> None:
        if not self._power_available(robot):
            return
        if robot.pending_target:
            if robot.edge:
                self._retreat_to_node(robot,dt)
                if robot.edge:
                    return
            target,avoid = robot.pending_target,robot.pending_avoid
            robot.pending_target = None
            robot.pending_avoid = set()
            self._route(robot,target,avoid)
            return
        if robot.yield_junction:
            if robot.edge:
                if not self._retreat_to_node(robot, dt):
                    # A following robot may make backing up unsafe. Clear the
                    # yield request and let this robot move forward to open a gap.
                    robot.yield_junction = None
                return
            junction = robot.yield_junction
            robot.yield_junction = None
            if robot.target and robot.target != junction:
                old_status = robot.status
                if self._route(robot, robot.target, {junction}):
                    robot.status = old_status
                    self.log(f"{robot.id} bypassed reserved junction {junction}")
            return
        if robot.route_index >= len(robot.path):
            if robot.target and robot.node != robot.target:
                self._route(robot, robot.target)
                return
            self._arrive(robot)
            return
        nxt = robot.path[robot.route_index]
        dest = self.graph.nodes[nxt]
        obs = next((o for o in self.obstacles.values()
                    if dist((dest.x, dest.y), (o["x"], o["y"])) < 1.8), None)
        if obs:
            self._set_wait(robot, f"{obs['category']} obstacle {obs['id']}")
            self._try_reroute(robot)
            return
        key = self._edge_key(robot.node, nxt)
        owner = self.edge_locks.get(key)
        if owner and owner != robot.id:
            self._set_wait(robot, f"Passage reserved by {owner}")
            holder = self.robots[owner]
            if not robot.edge and self._priority(holder) < self._priority(robot):
                if self._yield_active(robot, holder, key):
                    return
            if self.time - robot.blocked_since >= 3 and robot.target != nxt:
                old_status = robot.status
                if self._route(robot, robot.target, {nxt}):
                    robot.status = old_status
                    self.log(f"{robot.id} bypassed reserved passage toward {nxt}")
                robot.blocked_since = self.time
            return
        remaining = dist((robot.x, robot.y), (dest.x, dest.y))
        nearby = any(other.id != robot.id and dist((robot.x, robot.y), (other.x, other.y)) < DETECTION_RADIUS
                     for other in self.robots.values())
        nearby |= any(dist((robot.x, robot.y), (o["x"], o["y"])) < DETECTION_RADIUS for o in self.obstacles.values())
        speed = self.config["max_speed"] * (.55 if nearby else 1)
        step = min(speed * dt, remaining)
        if remaining > 1e-8:
            px = robot.x + (dest.x - robot.x) * step / remaining
            py = robot.y + (dest.y - robot.y) * step / remaining
        else:
            px, py = dest.x, dest.y
        obstruction = next((o for o in self.obstacles.values()
                            if dist((px, py), (o["x"], o["y"])) < 1.8), None)
        if obstruction:
            self._set_wait(robot, f"{obstruction['category']} obstacle {obstruction['id']}")
            self._try_reroute(robot)
            return
        inside_charge_entry = px < -10.5 and py < -38.5
        if inside_charge_entry and robot.status != "CHARGING":
            if self.charge_owner is None:
                departing = next((r for r in self.robots.values() if r.status == "MOVING_FROM_CHARGER"
                                  and r.x < -10.5 and r.y < -38.5), None)
                self.charge_owner = departing.id if departing else robot.id
            if self.charge_owner != robot.id:
                self._set_wait(robot, f"Charging entrance reserved by {self.charge_owner}")
                return
        # The station forecourt is one shared conflict area in the source
        # geometry. Admit one moving AMR at a time; others wait below it.
        if py >= 2.6:
            if self.top_owner and self.top_owner != robot.id:
                self._set_wait(robot, f"Station forecourt reserved by {self.top_owner}")
                if robot.edge:
                    robot.yield_junction = nxt if nxt != robot.target else None
                    self._retreat_to_node(robot, dt)
                return
            self.top_owner = robot.id
        if dest.kind == "junction" and dist((px, py), (dest.x, dest.y)) <= JUNCTION_RADIUS:
            junction_owner = self.junction_locks.get(nxt)
            if junction_owner and junction_owner != robot.id:
                self._set_wait(robot, f"Junction {nxt} reserved by {junction_owner}")
                robot.yield_junction = nxt
                if robot.edge:
                    self._retreat_to_node(robot, dt)
                return
            self.junction_locks[nxt] = robot.id
        heading = atan2(py-robot.y,px-robot.x) if step else robot.heading
        others = [other for other in self.robots.values() if other.id != robot.id
                  and ((dist((px, py), (other.x, other.y)) < MIN_SEPARATION
                        and dist((px, py), (other.x, other.y)) <= dist((robot.x, robot.y), (other.x, other.y)) + 1e-8)
                       or footprints_overlap(robot,other,(px,py),heading))]
        if others:
            if robot.status in ("MOVING_TO_DEPOT", "MOVING_FROM_CHARGER") and any(o.status == "IDLE" and o.node == robot.target for o in others):
                phase = robot.status
                self._dispatch_park(robot)
                if robot.target and robot.target != others[0].node:
                    robot.status = phase
                    self._route(robot, robot.target)
                    return
            for other in others:
                if other.status == "IDLE":
                    self._yield_idle(other, robot)
            winner = min([robot] + others, key=self._priority)
            self._set_wait(robot, f"Yielding to {winner.id}" if winner.id != robot.id
                           else f"Waiting for {others[0].id} to clear")
            if winner.id != robot.id and robot.edge:
                robot.yield_junction = others[0].node
                self._retreat_to_node(robot, dt)
            elif winner.id == robot.id:
                displaced = False
                for other in others:
                    if not other.edge and other.task_id:
                        displaced |= self._yield_active(other, robot, key)
                if not displaced and robot.edge and robot.node != others[0].node:
                    # An endpoint robot can be boxed in by traffic on both
                    # sides. The approaching robot must safely back out and
                    # take an alternate route instead of holding the passage.
                    robot.yield_junction = others[0].node
                    self._retreat_to_node(robot, dt)
            self._try_reroute(robot)
            return
        if not self._spend_power(robot, step * ENERGY_PER_METRE):
            return
        self.edge_locks[key] = robot.id
        robot.edge = key
        robot.heading = atan2(py - robot.y, px - robot.x) if step else robot.heading
        robot.x, robot.y = px, py
        robot.distance_m += step
        robot.velocity = step / dt
        robot.moving_seconds += dt
        self._clear_wait(robot)
        if self.charge_owner == robot.id and not inside_charge_entry:
            self.charge_owner = None
        if robot.waiting_reserved:
            wait = self.graph.nodes[robot.waiting_reserved]
            if robot.status != "MOVING_TO_YIELD" and dist((robot.x, robot.y), (wait.x, wait.y)) >= MIN_SEPARATION:
                self.waiting_locks.pop(robot.waiting_reserved, None)
                robot.waiting_reserved = None
        if self.top_owner == robot.id and robot.y < 2.6:
            self.top_owner = None
        if robot.status == "MOVING_FROM_CHARGER" and robot.charge_bay:
            bay = self.graph.nodes[robot.charge_bay]
            clear_region = robot.y-ROBOT_LENGTH/2 > -43.57 or robot.x-ROBOT_WIDTH/2 > -10.94
            if clear_region and dist((robot.x, robot.y), (bay.x, bay.y)) >= MIN_SEPARATION:
                self.charge_locks.pop(robot.charge_bay, None)
                robot.charge_bay = None
        for junction, holder in list(self.junction_locks.items()):
            p = self.graph.nodes[junction]
            if holder == robot.id and dist((robot.x, robot.y), (p.x, p.y)) > JUNCTION_RADIUS:
                del self.junction_locks[junction]
        if step + 1e-7 >= remaining:
            robot.node = nxt
            robot.route_index += 1
            self.edge_locks.pop(key, None)
            robot.edge = None
            if robot.shelf_to_release and robot.node != robot.shelf_to_release:
                self._release_shelf(robot)
            if robot.conveyor_to_release and robot.node != robot.conveyor_to_release:
                self._release_conveyor(robot)
            if robot.route_index >= len(robot.path):
                self._arrive(robot)

    def _retreat(self, robot: Robot, dt: float, winner: Robot) -> None:
        """Back a yielding AMR toward its previous safe node to clear a junction."""
        if not self._power_available(robot):
            return
        origin = self.graph.nodes[robot.node]
        length = dist((robot.x, robot.y), (origin.x, origin.y))
        if length < 1e-6:
            return
        step = min(SPEED * dt, length)
        px = robot.x + (origin.x - robot.x) * step / length
        py = robot.y + (origin.y - robot.y) * step / length
        if dist((px, py), (winner.x, winner.y)) <= dist((robot.x, robot.y),
                                                         (winner.x, winner.y)):
            return
        if any(dist((px, py), (other.x, other.y)) < MIN_SEPARATION or footprints_overlap(robot,other,(px,py))
               for other in self.robots.values() if other.id not in (robot.id, winner.id)):
            return
        if not self._spend_power(robot, step * ENERGY_PER_METRE):
            return
        robot.x, robot.y = px, py
        robot.distance_m += step
        robot.velocity = step / dt
        robot.moving_seconds += dt
        if step + 1e-7 >= length:
            self.edge_locks.pop(robot.edge, None)
            robot.edge = None

    def _retreat_to_node(self, robot: Robot, dt: float) -> bool:
        if not self._power_available(robot):
            return False
        origin = self.graph.nodes[robot.node]
        length = dist((robot.x, robot.y), (origin.x, origin.y))
        if length < 1e-6:
            self.edge_locks.pop(robot.edge, None)
            robot.edge = None
            return True
        step = min(SPEED * dt, length)
        px = robot.x + (origin.x - robot.x) * step / length
        py = robot.y + (origin.y - robot.y) * step / length
        if any(dist((px, py), (r.x, r.y)) < MIN_SEPARATION or footprints_overlap(robot,r,(px,py))
               for r in self.robots.values() if r.id != robot.id):
            return False
        if not self._spend_power(robot, step * ENERGY_PER_METRE):
            return False
        robot.x, robot.y = px, py
        robot.distance_m += step
        robot.velocity = step / dt
        robot.moving_seconds += dt
        if step + 1e-7 >= length:
            self.edge_locks.pop(robot.edge, None)
            robot.edge = None
        return True

    def _yield_idle(self, blocker: Robot, requester: Robot) -> None:
        """Move an idle robot out of a travel passage before traffic reaches it."""
        occupied = {r.node for r in self.robots.values() if r.id not in (blocker.id, requester.id)}
        occupied |= {r.target for r in self.robots.values() if r.id != blocker.id}
        occupied |= {n for n in self.graph.nodes if n.startswith("R")}
        candidates = [n for n, p in self.graph.nodes.items()
                      if p.kind in ("waiting", "parking") and n not in occupied and n != blocker.node]
        routes = []
        for goal in candidates:
            path = self.graph.path(blocker.node, goal, occupied | {requester.node})
            if path:
                length = sum(self.graph.edges[a][b] for a, b in zip(path, path[1:]))
                routes.append((length, goal, path))
        if not routes:
            return
        _, goal, path = min(routes)
        blocker.status = "MOVING_TO_PARK"
        blocker.target = goal
        blocker.path = path
        blocker.route_index = 1
        self.log(f"{blocker.id} yielding to {requester.id} at {goal}")

    def _yield_active(self, robot: Robot, holder: Robot, edge: tuple[str, str]) -> bool:
        if robot.resume_target or not robot.target:
            return False
        occupied = {r.node for r in self.robots.values() if r.id != robot.id}
        occupied |= {r.target for r in self.robots.values() if r.id != robot.id}
        occupied |= set(self.waiting_locks) | self._obstructed_nodes()
        occupied |= {n for n in self.graph.nodes if n.startswith("R")}
        occupied |= {s for s, owner in self.shelf_locks.items() if owner != robot.task_id}
        candidates = []
        for goal, point in self.graph.nodes.items():
            if point.kind != "waiting" or goal in occupied or goal == "CHARGE_WAIT":
                continue
            path = self.graph.path(robot.node, goal, occupied, blocked_edges={edge} | self._obstructed_edges())
            if path:
                length = sum(self.graph.edges[a][b] for a, b in zip(path, path[1:]))
                candidates.append((0 if point.x > robot.x else 1, length, goal, path))
        if not candidates:
            return False
        _, _, goal, path = min(candidates)
        robot.resume_target, robot.resume_status = robot.target, robot.status
        robot.status, robot.target, robot.path, robot.route_index = "MOVING_TO_YIELD", goal, path, 1
        robot.yield_edge, robot.waiting_reserved = edge, goal
        self.waiting_locks[goal] = robot.id
        self.log(f"{robot.id} reserved {goal}; yielding to {holder.id}", "warning")
        return True

    def _try_reroute(self, robot: Robot) -> None:
        if self.time - robot.blocked_since < 3 or not robot.target or robot.edge:
            return
        occupied = {r.node for r in self.robots.values() if r.id != robot.id
                    and dist((r.x, r.y), (self.graph.nodes[r.node].x,
                                        self.graph.nodes[r.node].y)) < 0.4}
        old_status = robot.status
        if self._route(robot, robot.target, occupied):
            robot.status = old_status
            robot.blocked_since = self.time
            self.log(f"{robot.id} recalculated route around blocked passage")
        else:
            robot.status = old_status
            robot.blocked_since = self.time

    def _arrive(self, robot: Robot) -> None:
        task = self.tasks.get(robot.task_id or "")
        if robot.status == "MOVING_TO_DESTINATION" and task:
            self._complete(task, robot)
        elif robot.status == "MOVING_TO_RESUME":
            robot.status = robot.charge_resume_status or "IDLE"
            robot.charge_resume_status = robot.charge_resume_target = None
            robot.action_started = self.time
            robot.hold_until = self.time + (self.config["packing_seconds"] if robot.status == "PACKING_PACKAGE" else self.config["operation_seconds"])
            self.log(f"{robot.id} resumed {robot.status.lower().replace('_', ' ')} after charging")
        elif robot.status == "MOVING_TO_PICKUP" and task:
            robot.status = "PICKING_PACKAGE"
            task.state = "IN_PROGRESS"
            robot.action_started = self.time
            robot.hold_until = self.time + self.config["operation_seconds"]
        elif robot.status == "MOVING_TO_SHELF" and task:
            if self.shelf_locks.get(self.slots[task.slot].shelf) != task.id:
                robot.status = "ERROR"
                self.log(f"{robot.id}: shelf reservation missing", "error")
            else:
                robot.status = "STORING_PACKAGE"
                robot.action_started = self.time
                robot.hold_until = self.time + self.config["operation_seconds"]
        elif robot.status == "MOVING_TO_RETRIEVAL" and task:
            if self.shelf_locks.get(self.slots[task.slot].shelf) != task.id:
                robot.status = "ERROR"
                self.log(f"{robot.id}: shelf reservation missing", "error")
            else:
                robot.status = "RETRIEVING_PACKAGE"
                task.state = "IN_PROGRESS"
                robot.action_started = self.time
                robot.hold_until = self.time + self.config["operation_seconds"]
        elif robot.status == "MOVING_TO_PACKING" and task:
            robot.status = "PACKING_PACKAGE"
            robot.action_started = self.time
            robot.hold_until = self.time + self.config["packing_seconds"]
            self.packages[task.package_id]["stage"] = "PACKING"
            self.log(f"{robot.id} packing {task.package_id} at PACKING")
        elif robot.status == "MOVING_TO_CONVEYOR" and task:
            if self.conveyor_locks.get(task.conveyor or "") != task.id:
                robot.status = "ERROR"
                self.log(f"{robot.id}: conveyor reservation missing", "error")
            else:
                robot.status = "DEPOSITING_PACKAGE"
                robot.action_started = self.time
                robot.hold_until = self.time + self.config["operation_seconds"]
        elif robot.status == "CLEARING_SHELF" and task:
            self._release_shelf(robot)
            self._complete(task, robot)
        elif robot.status == "CLEARING_CONVEYOR" and task:
            self._release_conveyor(robot)
            if robot.conveyor_to_release:
                robot.status = "WAITING_CONVEYOR_CLEAR"
            else:
                self._complete(task, robot)
        elif robot.status == "MOVING_TO_CHARGER":
            if self.charge_locks.get(robot.target or "") == robot.id:
                robot.status = "CHARGING"
                robot.velocity = 0
                if self.charge_owner == robot.id:
                    self.charge_owner = None
                self.log(f"{robot.id} charging at {robot.target}")
        elif robot.status == "MOVING_TO_CHARGE_WAIT":
            robot.status = "WAITING_FOR_CHARGER"
        elif robot.status == "MOVING_TO_YIELD":
            robot.status = "YIELDING"
        elif robot.status == "MOVING_FROM_CHARGER":
            if robot.charge_bay:
                self.charge_locks.pop(robot.charge_bay, None)
                robot.charge_bay = None
            robot.status = "IDLE"
            robot.velocity = 0
            if self.top_owner == robot.id:
                self.top_owner = None
            if self.charge_owner == robot.id:
                self.charge_owner = None
            if robot.charge_resume_status:
                resume = robot.charge_resume_status
                destination = robot.charge_resume_target
                robot.status = resume if resume.startswith(("MOVING_", "CLEARING_")) else "MOVING_TO_RESUME"
                self._route(robot, destination)
                if robot.node == destination and robot.status == "MOVING_TO_RESUME":
                    self._arrive(robot)
                elif robot.status != "MOVING_TO_RESUME":
                    robot.charge_resume_status = robot.charge_resume_target = None
                self.log(f"{robot.id} returning to {destination} after charging")
        elif robot.status in ("MOVING_TO_PARK", "MOVING_TO_DEPOT"):
            robot.status = "IDLE"
            robot.velocity = 0
            if self.top_owner == robot.id:
                self.top_owner = None

    def _release_shelf(self, robot: Robot) -> None:
        if not robot.shelf_to_release:
            return
        task = self.tasks.get(robot.task_id or "")
        if task and self.shelf_locks.get(robot.shelf_to_release) == task.id:
            del self.shelf_locks[robot.shelf_to_release]
            self.slots[task.slot].reserved_by = None
            self.log(f"{task.id} released shelf {robot.shelf_to_release}")
        robot.shelf_to_release = None

    def _release_conveyor(self, robot: Robot) -> None:
        if not robot.conveyor_to_release:
            return
        task = self.tasks.get(robot.task_id or "")
        if any(p["task"] == (task.id if task else "") and p["progress"] < .22 for p in self.conveyor_packages):
            return
        if task and self.conveyor_locks.get(robot.conveyor_to_release) == task.id:
            del self.conveyor_locks[robot.conveyor_to_release]
            self.log(f"{task.id} released {robot.conveyor_to_release}")
        robot.conveyor_to_release = None

    def _complete(self, task: Task, robot: Robot) -> None:
        task.final_battery = round(robot.battery, 2)
        task.final_location = robot.node
        if task.kind == "OUTBOUND" and self.packages.get(task.package_id, {}).get("stage") != "DELIVERED":
            task.state = "IN_TRANSIT"
            self.log(f"{task.id} robot clear; package travelling to delivery")
        else:
            task.state = "COMPLETED"
            task.completed = round(self.time, 3)
            self.log(f"{task.id} completed by {robot.id} at {robot.battery:.0f}% battery")
        robot.task_id = None
        robot.target = None
        robot.path = []
        robot.status = "IDLE"
        robot.velocity = 0
        if robot.battery <= self.config["charge_trigger"]:
            self._dispatch_charger(robot)
        # Queued work gets first chance to claim this robot in the same tick.
        # The idle pass below sends it home only if no eligible order exists.

    def _dispatch_park(self, robot: Robot) -> None:
        home = f"DEPOT_{int(robot.id[-2:])}"
        if robot.node == home or self._safe_current_dock(robot):
            return
        occupied = {r.target for r in self.robots.values() if r.id != robot.id}
        occupied |= {r.node for r in self.robots.values() if r.id != robot.id}
        blocked = self._obstructed_nodes() | set(self.shelf_locks)
        point = self.graph.nodes[home]
        if home in occupied or home in blocked:
            return
        if any(dist((point.x, point.y), (r.x, r.y)) < MIN_SEPARATION
               for r in self.robots.values() if r.id != robot.id):
            return
        path = self.graph.path(robot.node, home, blocked, blocked_edges=self._obstructed_edges())
        if path:
            robot.status = "MOVING_TO_DEPOT"
            self._route(robot, home)
            self.log(f"{robot.id} returning to its depot position {home}")

    def _dispatch_charger(self, robot: Robot) -> None:
        if robot.status not in ("IDLE", "WAITING_FOR_CHARGER"):
            return
        home = f"DEPOT_{int(robot.id[-2:])}"
        if any(other.id != robot.id and (other.node == home or other.target == home)
               for other in self.robots.values()):
            robot.status = "WAITING_FOR_CHARGER"
            return
        self.charge_locks[home] = robot.id
        robot.charge_bay = home
        if robot.node == home:
            robot.status = "CHARGING"
            robot.velocity = 0
            return
        robot.status = "MOVING_TO_CHARGER"
        if self._route(robot, home):
            self.log(f"{robot.id} routed to its charging/depot position {home}")
        else:
            self.charge_locks.pop(home, None)
            robot.charge_bay = None
            robot.status = "WAITING_FOR_CHARGER"

    def _process_action(self, robot: Robot) -> None:
        task = self.tasks.get(robot.task_id or "")
        if not task or self.time + 1e-9 < robot.hold_until:
            return
        if robot.status != "PACKING_PACKAGE" and not self._spend_power(robot, 0.2):
            return
        slot = self.slots[task.slot]
        if robot.status == "PICKING_PACKAGE":
            self.package_sequence += 1
            task.package_id = f"PKG-{self.package_sequence:04d}"
            self.packages[task.package_id] = {"id": task.package_id, "sku": task.sku,
                "stage": "CARRIED", "robot": robot.id, "created": round(self.time, 3), "task": task.id}
            robot.carrying = True
            robot.status = "MOVING_TO_SHELF"
            self._route(robot, slot.shelf)
            self.log(f"{robot.id} picked {task.package_id}; visible pickup stack unchanged")
        elif robot.status == "STORING_PACKAGE":
            slot.sku, slot.package_id = task.sku, task.package_id
            self.packages[task.package_id].update(stage="STORED", slot=slot.id, robot=None, stored=round(self.time, 3))
            robot.carrying = False
            robot.shelf_to_release = slot.shelf
            robot.status = "CLEARING_SHELF"
            self._route(robot, self._clear_point(slot.shelf))
            self.log(f"{robot.id} stored {task.package_id} in {slot.id}")
        elif robot.status == "RETRIEVING_PACKAGE":
            robot.carrying = True
            task.package_id = slot.package_id
            self.packages.setdefault(task.package_id, {"id": task.package_id, "sku": task.sku}).update(stage="CARRIED", robot=robot.id, slot=None, task=task.id, retrieved=round(self.time, 3))
            slot.sku = slot.package_id = None
            robot.shelf_to_release = slot.shelf
            self.log(f"{robot.id} retrieved {task.package_id} from {slot.id}")
            self._request_conveyor(robot, task)
        elif robot.status == "PACKING_PACKAGE":
            task.packed = round(self.time, 3)
            self.packages[task.package_id].update(stage="PACKED", packed=task.packed)
            robot.status = "MOVING_TO_CONVEYOR"
            self._route(robot, task.conveyor)
            self.log(f"{task.package_id} packed; {robot.id} approaching {task.conveyor}")
        elif robot.status == "DEPOSITING_PACKAGE":
            robot.carrying = False
            self.conveyor_packages.append({"id": task.package_id, "task": task.id,
                                           "progress": 0.0, "lane": task.conveyor})
            task.deposited = round(self.time, 3)
            self.packages[task.package_id].update(stage="CONVEYOR", robot=None, deposited=task.deposited, lane=task.conveyor)
            robot.conveyor_to_release = task.conveyor
            robot.status = "CLEARING_CONVEYOR"
            self._route(robot, "BN" if task.conveyor != "CONV_1" else "AN")
            self.log(f"{robot.id} deposited {task.package_id} on {task.conveyor}")

    def _clear_point(self, shelf: str) -> str:
        col, row = shelf[0], int(shelf[-1])
        # Use either adjacent cross aisle if the preferred one is obstructed.
        top = f"{col}{('N', '1', '2', '3')[row - 1]}"
        bottom = f"{col}{('1', '2', '3', 'S')[row - 1]}"
        return bottom if top in self._obstructed_nodes() else top

    def _request_conveyor(self, robot: Robot, task: Task) -> None:
        choices = ([task.requested_conveyor] if task.requested_conveyor
                   else [f"CONV_{i}" for i in (1, 2, 3)])
        available = [lane for lane in choices if lane not in self.conveyor_locks]
        lane = min(available,
                   key=lambda n: (dist((robot.x, robot.y),
                                       (self.graph.nodes[n].x, self.graph.nodes[n].y)), n),
                   default=None)
        if lane is None:
            robot.status = "WAITING_FOR_LANE"
            self._set_wait(robot, f"Conveyor {task.requested_conveyor} reserved; waiting for release" if task.requested_conveyor else "All conveyor lanes reserved")
            # Clear the protected shelf before waiting at a cross aisle.
            self._route(robot, self._clear_point(self.slots[task.slot].shelf))
            return
        self.conveyor_locks[lane] = task.id
        task.conveyor = lane
        robot.status = "MOVING_TO_PACKING"
        self._route(robot, "PACKING")
        self.log(f"{task.id} reserved {lane}")

    def step(self, dt: float = TICK) -> None:
        dt = min(max(float(dt), 0.001), 0.5)
        self.time = round(self.time + dt, 4)
        # Recover an orphan only once its recorded owner is physically clear.
        # This also protects against interrupted/replanned parking maneuvers.
        for key,owner in list(self.edge_locks.items()):
            holder = self.robots.get(owner)
            if holder is None or holder.edge == key:
                continue
            a,b = [self.graph.nodes[n] for n in key]
            dx,dy = b.x-a.x,b.y-a.y
            fraction = max(0,min(1,((holder.x-a.x)*dx+(holder.y-a.y)*dy)/(dx*dx+dy*dy)))
            if dist((holder.x,holder.y),(a.x+fraction*dx,a.y+fraction*dy)) >= MIN_SEPARATION:
                self.edge_locks.pop(key,None)
                self.log(f"Recovered unoccupied passage {key[0]}–{key[1]}")
        for package in self.conveyor_packages:
            package["progress"] = min(1.0, package["progress"] + dt / self.config["conveyor_seconds"])
            if package["progress"] >= 1:
                self.packages[package["id"]].update(stage="DELIVERED", delivered=round(self.time, 3))
                task = self.tasks[package["task"]]
                if task.state == "IN_TRANSIT":
                    task.state, task.completed = "COMPLETED", round(self.time, 3)
                self.log(f"{package['id']} reached delivery; {task.id} transport complete")
        self.conveyor_packages = [p for p in self.conveyor_packages if p["progress"] < 1.0]
        charger_phases = {"MOVING_TO_CHARGER", "MOVING_TO_CHARGE_WAIT", "WAITING_FOR_CHARGER",
                          "CHARGING", "MOVING_FROM_CHARGER", "POWER_DEPLETED", "ERROR"}
        for robot in self.robots.values():
            if robot.battery <= 0:
                self._power_available(robot)
            elif robot.battery <= self.config["charge_trigger"] and robot.status not in charger_phases | {"IDLE"}:
                if robot.task_id and not robot.charge_resume_status:
                    robot.charge_resume_status = robot.status
                    robot.charge_resume_target = robot.target or robot.node
                    self.log(f"{robot.id} reached {robot.battery:.1f}%; suspending {robot.task_id} for charging", "warning")
                robot.status = "IDLE"
                self._dispatch_charger(robot)
        for robot in sorted(self.robots.values(), key=lambda r: dist((r.x,r.y),
                (self.graph.nodes[f"DEPOT_{int(r.id[-2:])}"].x,
                 self.graph.nodes[f"DEPOT_{int(r.id[-2:])}"].y))):
            robot.velocity = 0
            if robot.block_reason or robot.status.startswith("WAITING"):
                robot.waiting_seconds += dt
            if robot.conveyor_to_release:
                point = self.graph.nodes[robot.conveyor_to_release]
                if dist((robot.x, robot.y), (point.x, point.y)) >= MIN_SEPARATION:
                    self._release_conveyor(robot)
            if robot.status == "CHARGING":
                if not self._in_charging_area(robot):
                    robot.status = "IDLE"
                    continue
                robot.battery = min(100, robot.battery + CHARGE_RATE * dt)
                if robot.battery >= self.config["recharge_target"]:
                    if robot.charge_resume_status:
                        robot.status = "MOVING_FROM_CHARGER"
                        self._route(robot, f"DEPOT_ENTRY_{int(robot.id[-2:])}")
                    else:
                        self.charge_locks.pop(robot.charge_bay, None)
                        robot.charge_bay = None
                        robot.status = "IDLE"
                    self.log(f"{robot.id} charged to {robot.battery:.0f}% at its depot position")
            elif robot.status == "IDLE" and self._actively_charging(robot):
                robot.battery = min(100, robot.battery + CHARGE_RATE * dt)
            elif robot.status == "IDLE" and robot.battery <= self.config["charge_trigger"]:
                self._dispatch_charger(robot)
            elif robot.status == "WAITING_FOR_CHARGER":
                self._dispatch_charger(robot)
            elif robot.status == "YIELDING" and robot.yield_edge not in self.edge_locks:
                robot.status = robot.resume_status
                target = robot.resume_target
                robot.resume_target = robot.resume_status = robot.yield_edge = None
                self._route(robot, target)
            elif robot.status == "WAITING_CONVEYOR_CLEAR" and not robot.conveyor_to_release:
                self._complete(self.tasks[robot.task_id], robot)
            elif robot.status == "WAITING_FOR_LANE" and robot.task_id:
                task = self.tasks[robot.task_id]
                if robot.route_index < len(robot.path):
                    self._move(robot, dt)
                elif any(lane not in self.conveyor_locks for lane in
                         ([task.requested_conveyor] if task.requested_conveyor else [f"CONV_{i}" for i in (1, 2, 3)])):
                    self._request_conveyor(robot, task)
        self._queue_assignments()
        for robot in self.robots.values():
            if robot.status == "IDLE" and not robot.task_id and robot.battery > self.config["charge_trigger"]:
                self._dispatch_park(robot)
        for robot in sorted(self.robots.values(), key=self._priority):
            if robot.status.startswith("MOVING_") or robot.status.startswith("CLEARING_"):
                self._move(robot, dt)
            elif robot.status in ("PICKING_PACKAGE", "STORING_PACKAGE",
                                  "RETRIEVING_PACKAGE", "DEPOSITING_PACKAGE", "PACKING_PACKAGE"):
                self._process_action(robot)
        self.telemetry.observe(self)

    def run(self, seconds: float) -> None:
        for _ in range(round(seconds / TICK)):
            self.step()

    def snapshot(self) -> dict:
        def robot_data(r: Robot) -> dict:
            task = self.tasks.get(r.task_id or "")
            near = [other.id for other in self.robots.values() if other.id != r.id
                    and dist((r.x, r.y), (other.x, other.y)) <= DETECTION_RADIUS]
            seen = [obs["id"] for obs in self.obstacles.values()
                    if dist((r.x, r.y), (obs["x"], obs["y"])) <= DETECTION_RADIUS]
            return {"id": r.id, "source_object": r.source_object, "x": round(r.x, 3),
                    "y": round(r.y, 3), "heading": round(r.heading, 3),
                    "node": r.node, "lane": r.node[0] if r.node[0] in "LABC" else "station",
                    "battery": round(r.battery, 2), "status": r.status,
                    "task": r.task_id, "task_type": task.kind if task else None,
                    "assigned": task.assigned if task else None,
                    "carrying": r.carrying, "target": r.target,
                    "route": r.path[r.route_index:] if r.path else [],
                    "block_reason": r.block_reason, "near_robots": near,
                    "detected_obstacles": seen, "reservation": list(r.edge) if r.edge else None,
                    "charge_bay": r.charge_bay, "docked": self._docked(r),
                    "charging": self._actively_charging(r)}
        def enriched_robot(r):
            data = robot_data(r)
            task = self.tasks.get(r.task_id or "")
            data.update(distance_m=round(r.distance_m, 2), velocity=round(r.velocity, 2),
                waiting_seconds=round(r.waiting_seconds, 2), slot=task.slot if task else None,
                conveyor=task.conveyor if task else None, package_id=task.package_id if task else None,
                action_progress=max(0, min(1, (self.time-r.action_started)/(r.hold_until-r.action_started))) if r.hold_until>r.action_started else 0,
                priority=list(self._priority(r))[:2],
                coordination=[{"id": other.id, "task": other.task_id, "next": other.path[other.route_index] if other.route_index<len(other.path) else None,
                    "carrying": other.carrying, "battery": round(other.battery, 2), "blocked": bool(other.block_reason)}
                    for other in self.robots.values() if other.id in data["near_robots"]])
            return data
        packages = [p.copy() for p in self.packages.values()]
        floor_z = self.graph.model.get("floor_z", 1.825)
        for package in packages:
            robot = self.robots.get(package.get("robot"))
            if robot:
                position = [robot.x, robot.y, floor_z+.87]
                task = self.tasks.get(robot.task_id)
                if robot.status == "STORING_PACKAGE" and task and self.slots[task.slot].position:
                    target = self.slots[task.slot].position
                    progress = min(1, max(0, (self.time-robot.action_started)/(robot.hold_until-robot.action_started)))
                    position = [a+(b-a)*progress for a,b in zip(position,target)]
                elif robot.status == "DEPOSITING_PACKAGE" and task:
                    x = {"CONV_1": -8, "CONV_2": -3.8, "CONV_3": -.3}[task.conveyor]
                    target = [x,13.3,2.31]
                    progress = min(1, max(0, (self.time-robot.action_started)/(robot.hold_until-robot.action_started)))
                    position = [a+(b-a)*progress for a,b in zip(position,target)]
                package["position"] = position
            elif package["stage"] == "STORED" and package.get("slot"):
                position = self.slots[package["slot"]].position
                retrieving = next((r for r in self.robots.values() if r.status == "RETRIEVING_PACKAGE"
                                   and self.tasks[r.task_id].slot == package["slot"]), None)
                if position and retrieving:
                    target = [retrieving.x,retrieving.y,floor_z+.87]
                    progress = min(1, max(0, (self.time-retrieving.action_started)/(retrieving.hold_until-retrieving.action_started)))
                    position = [a+(b-a)*progress for a,b in zip(position,target)]
                package["position"] = position
            elif package["stage"] == "CONVEYOR":
                moving = next((p for p in self.conveyor_packages if p["id"] == package["id"]), None)
                if moving:
                    x = {"CONV_1": -8, "CONV_2": -3.8, "CONV_3": -.3}[moving["lane"]]
                    package["position"] = [x+(1.45-x)*moving["progress"],13.3,2.31]
            elif package["stage"] == "DELIVERED":
                index = [p["id"] for p in packages if p["stage"] == "DELIVERED"].index(package["id"])
                package["position"] = [2.5+index%6*.8,11.5-(index//6)%3*.85,floor_z+.25]
        history = self.telemetry.samples[::max(1,(len(self.telemetry.samples)+239)//240)]
        if self.telemetry.samples and history[-1] != self.telemetry.samples[-1]:
            history = history + [self.telemetry.samples[-1]]
        return {"run_id": self.run_id, "time": round(self.time, 2), "geometry": self.graph.as_dict(),
                "robots": [enriched_robot(r) for r in self.robots.values()],
                "tasks": [vars(t).copy() for t in self.tasks.values()],
                "slots": [vars(s).copy() for s in self.slots.values()],
                "locks": {"shelves": self.shelf_locks.copy(),
                          "conveyors": self.conveyor_locks.copy(),
                          "charging": self.charge_locks.copy(),
                          "junctions": self.junction_locks.copy(),
                          "waiting": self.waiting_locks.copy(),
                          "edges": [[*edge, owner] for edge, owner in self.edge_locks.items()],
                          "forecourt": self.top_owner, "charging_entry": self.charge_owner},
                "obstacles": list(self.obstacles.values()),
                "conveyor_packages": [p.copy() for p in self.conveyor_packages],
                "packages": packages,
                "metrics": self.telemetry.metrics(self), "history": history,
                "events": self.events[-60:],
                "config": {"robot_width": ROBOT_WIDTH, "robot_length": ROBOT_LENGTH,
                           "detection_radius": DETECTION_RADIUS,
                           "minimum_separation": MIN_SEPARATION,
                           **self.config}}
