"""Start the simulation dashboard with only the Python standard library."""

from __future__ import annotations

import argparse
import json
import threading
import time
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from automation import AutomationRuntime
from sim.engine import TICK, Warehouse

ROOT = Path(__file__).parent.resolve()
WEB = ROOT / "web"


def source_product_map():
    catalog = json.loads((ROOT / "automation_catalog.json").read_text(encoding="utf-8"))
    return {product["shelf"]: product["id"] for product in catalog["products"]}


class SimulationServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Runtime:
    def __init__(self, demo: bool, speed: float):
        self.lock = threading.RLock()
        self.warehouse = Warehouse(demo)
        if not demo:
            self.warehouse.seed_source_stock(source_product_map())
        self.paused = True
        self.speed = speed
        self.running = True
        self.had_activity = False

    def advance(self):
        with self.lock:
            if self.paused:
                return
            self.warehouse.step(TICK)
            active = any(r.status != "IDLE" or self.warehouse._actively_charging(r)
                         or not self.warehouse._in_charging_area(r)
                         for r in self.warehouse.robots.values())
            pending = any(t.state not in ("COMPLETED","CANCELLED","FAILED") for t in self.warehouse.tasks.values())
            self.had_activity |= active or pending
            if self.had_activity and not active and not pending:
                self.paused = True
                self.had_activity = False
                self.warehouse.log("Run settled: fleet idle and all requests terminal")

    def loop(self):
        while self.running:
            started = time.monotonic()
            self.advance()
            delay = max(0.005, TICK / max(self.speed, 0.1) - (time.monotonic() - started))
            time.sleep(delay)


class Handler(SimpleHTTPRequestHandler):
    runtime: Runtime
    automation: AutomationRuntime | None = None

    def log_message(self, format, *args):
        if self.path != "/api/state":
            super().log_message(format, *args)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def translate_path(self, path):
        if urlparse(path).path == "/automation":
            return super().translate_path("/automation.html")
        if urlparse(path).path.startswith("/vendor/"):
            base = (ROOT / "node_modules" / "three").resolve()
            resolved = (base / urlparse(path).path.removeprefix("/vendor/")).resolve()
            if resolved.is_relative_to(base):
                return str(resolved)
            return str(WEB / "missing")
        return super().translate_path(path)

    def _json(self, value, status=200):
        data = json.dumps(value, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/api/automation/state":
            self._json(self.automation.snapshot())
        elif route.startswith("/api/automation/orders/"):
            order_id = route.removeprefix("/api/automation/orders/")
            with self.automation.lock:
                order = self.automation.orders.get(order_id)
                self._json(order.copy() if order else {"error":"Order not found"},
                           200 if order else 404)
        elif route in ("/api/state", "/api/report"):
            with self.runtime.lock:
                state = self.runtime.warehouse.snapshot()
                state["paused"] = self.runtime.paused
                state["speed"] = self.runtime.speed
                if route == "/api/report":
                    state["events"] = self.runtime.warehouse.events
                    state["history"] = self.runtime.warehouse.telemetry.samples
            self._json(state)
        else:
            super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/"):
            self._json({"error": "Not found"}, 404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 65536:
                raise ValueError("Request too large")
            body = json.loads(self.rfile.read(size) or b"{}")
            action = urlparse(self.path).path.removeprefix("/api/")
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            if action.startswith("automation/"):
                if self.automation is None:
                    raise ValueError("Automation runtime is unavailable")
                if action == "automation/orders":
                    result = self.automation.ingest(body)
                elif action == "automation/source":
                    result = self.automation.set_source(body.get("url", ""),
                        body.get("interval_seconds", 5), body.get("bearer_token"))
                elif action == "automation/source/poll":
                    result = self.automation.poll_once()
                else:
                    self._json({"error":"Not found"}, 404)
                    return
                self._json(result, 200 if result.get("duplicate") else 202 if action == "automation/orders" else 200)
                return
            with self.runtime.lock:
                w = self.runtime.warehouse
                if action == "task":
                    sku = str(body.get("sku", "")).strip()
                    if not sku or len(sku) > 40:
                        raise ValueError("Enter a SKU of 1–40 characters")
                    kind = str(body.get("kind", "")).upper()
                    if kind == "INBOUND":
                        result = {"task_id": w.request_inbound(sku)}
                    elif kind == "OUTBOUND":
                        result = {"task_id": w.request_outbound(sku)}
                    else:
                        raise ValueError("kind must be INBOUND or OUTBOUND")
                elif action == "add-robot":
                    robot = w.add_robot()
                    result = {"robot_id": robot.id, "charging_slot": robot.depot_slot,
                              "fleet_size": len(w.robots), "capacity": len(w.depot_ids)}
                elif action == "manual-job":
                    result = {"task_id": w.request_manual(
                        str(body.get("kind", "")).upper(),
                        str(body.get("robot_id", "")),
                        str(body.get("slot_id", "")) or None,
                        str(body.get("sku", "")),
                        str(body.get("conveyor", "")) or None,
                        str(body.get("destination", "")) or None)}
                elif action == "obstacle":
                    if body.get("remove"):
                        w.remove_obstacle(str(body["remove"]))
                        result = {"removed": body["remove"]}
                    else:
                        x, y = float(body["x"]), float(body["y"])
                        x0, y0, x1, y1 = w.graph.as_dict()["floor"]
                        if not (x0 <= x <= x1 and y0 <= y <= y1):
                            raise ValueError("Obstacle must be within the floor")
                        if any(a-.4 <= x <= c+.4 and b-.4 <= y <= d+.4 for a,b,c,d in w.graph.as_dict()["racks"]):
                            raise ValueError("Place obstacles on clear floor outside the storage racks")
                        category = str(body.get("category", "unknown"))
                        if category not in ("human", "debris", "equipment", "unknown"):
                            raise ValueError("Invalid obstacle category")
                        result = {"obstacle_id": w.add_obstacle(x, y, category)}
                elif action == "control":
                    if "paused" in body:
                        self.runtime.paused = bool(body["paused"])
                    if "speed" in body:
                        speed = float(body["speed"])
                        if not 0.1 <= speed <= 20:
                            raise ValueError("Speed must be between 0.1 and 20")
                        self.runtime.speed = speed
                    if body.get("step"):
                        w.step(TICK)
                    result = {"paused": self.runtime.paused, "speed": self.runtime.speed}
                elif action == "batch":
                    count = int(body.get("count", 1))
                    prefix = str(body.get("prefix", "")).strip()
                    if not 1 <= count <= 24 or not prefix or len(prefix) > 30:
                        raise ValueError("Enter 1–24 packages and a SKU prefix of 1–30 characters")
                    result = {"tasks": []}
                    for i in range(count):
                        sku = f"{prefix}-{i+1:02d}"
                        result["tasks"].append(w.request_inbound(sku))
                        if body.get("retrieve"):
                            result["tasks"].append(w.request_outbound(sku))
                elif action == "cancel":
                    task = w.tasks[str(body["task_id"])]
                    if task.state != "QUEUED":
                        raise ValueError("Only queued requests can be cancelled")
                    task.state = "CANCELLED"
                    w.log(f"{task.id} cancelled by operator")
                    result = {"cancelled": task.id}
                elif action == "configure":
                    if not self.runtime.paused:
                        raise ValueError("Pause the run before changing parameters")
                    limits = {"max_speed": (.2, 3), "charge_trigger": (30, 40),
                              "recharge_target": (50, 100), "conveyor_seconds": (8, 60),
                              "operation_seconds": (1, 10), "packing_seconds": (1, 15)}
                    updates = {}
                    for key, value in body.items():
                        if key not in limits:
                            raise ValueError(f"Unknown parameter {key}")
                        value = float(value)
                        low, high = limits[key]
                        if not low <= value <= high:
                            raise ValueError(f"{key} must be between {low} and {high}")
                        updates[key] = value
                    w.config.update(updates)
                    w.log("Simulation parameters updated by operator")
                    result = {"config": w.config}
                elif action == "reset":
                    battery = float(body.get("initial_battery", 100))
                    if not 15 <= battery <= 100:
                        raise ValueError("Initial charge must be 15–100 percent to retain enough energy for the boundary charging route")
                    fresh = Warehouse(initial_battery=battery)
                    fresh.seed_source_stock(source_product_map())
                    self.runtime.warehouse = fresh
                    self.runtime.paused = True
                    self.runtime.had_activity = False
                    result = {"reset": True}
                else:
                    self._json({"error": "Not found"}, 404)
                    return
            self._json(result)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, 400)


def main():
    parser = argparse.ArgumentParser(description="AMR warehouse simulation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Simulation seconds per wall-clock second")
    parser.add_argument("--empty", action="store_true", help="Compatibility flag; source-model stock is always loaded")
    args = parser.parse_args()
    runtime = Runtime(False, args.speed)
    automation = AutomationRuntime(speed=args.speed)
    Handler.runtime = runtime
    Handler.automation = automation
    try:
        server = SimulationServer((args.host, args.port), Handler)
    except OSError as exc:
        raise SystemExit(f"Cannot start on port {args.port}: {exc}. Stop the existing warehouse server before restarting.") from exc
    threading.Thread(target=runtime.loop, daemon=True).start()
    threading.Thread(target=automation.loop, daemon=True).start()
    threading.Thread(target=automation.poll_loop, daemon=True).start()
    print(f"Warehouse dashboard: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.running = False
        automation.running = False
        server.server_close()


if __name__ == "__main__":
    main()
