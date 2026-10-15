"""Separate API-fed warehouse simulation, with product-specific shelf groups."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sim.engine import TICK, Warehouse

CATALOG = Path(__file__).with_name("automation_catalog.json")
DEFAULT_SOURCE_URL = "http://192.168.56.1:5000/api/orders"
OPERATIONS = {"STORE":"STORE", "STORAGE":"STORE", "INBOUND":"STORE", "PUTAWAY":"STORE",
              "DELIVER":"DELIVER", "DELIVERY":"DELIVER", "OUTBOUND":"DELIVER", "FULFILL":"DELIVER"}


def field(raw, *names):
    return next((raw[name] for name in names if raw.get(name) is not None), None)


def key(value):
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


class AutomationRuntime:
    def __init__(self, catalog=CATALOG, speed=1.0):
        self.lock = threading.RLock()
        self.warehouse = Warehouse()
        self.speed = speed
        self.running = True
        self.orders = {}
        self.source_url = DEFAULT_SOURCE_URL
        self.source_token = ""
        self.source_interval = 5.0
        self.source_error = ""
        self.last_poll = None
        self.products = {}
        self.lookup = {}
        used_shelves = set()
        for entry in json.loads(Path(catalog).read_text(encoding="utf-8"))["products"]:
            product = {name: str(entry[name]).strip() for name in ("id", "name", "shelf")}
            slots = [slot.id for slot in self.warehouse.slots.values() if slot.shelf == product["shelf"]]
            if (not all(product.values()) or product["id"] in self.products
                    or product["shelf"] in used_shelves or not slots
                    or not all(self.warehouse.slots[sid].validated_vacant for sid in slots)):
                raise ValueError(f"Invalid or overlapping product shelf mapping: {entry}")
            product["slots"] = slots
            self.products[product["id"]] = product
            used_shelves.add(product["shelf"])
            for label in (product["id"], product["name"]):
                normalized = key(label)
                if normalized in self.lookup and self.lookup[normalized] != product["id"]:
                    raise ValueError(f"Ambiguous product label: {label}")
                self.lookup[normalized] = product["id"]
        self.warehouse.seed_source_stock({p["shelf"]: p["id"] for p in self.products.values()})

    def parse_order(self, raw):
        if not isinstance(raw, dict):
            raise ValueError("Each order must be a JSON object")
        order_id = str(field(raw, "orderid", "orderId", "order_id") or "").strip()
        name = str(field(raw, "productname", "productName", "product_name", "product") or "").strip()
        product_ref = field(raw, "productid", "productId", "product_id", "sku")
        product_id = self.lookup.get(key(product_ref)) if product_ref else self.lookup.get(key(name))
        requested_operation = field(raw, "operation", "orderType", "order_type", "type")
        operation = ("DELIVER" if requested_operation is None else
                     OPERATIONS.get(str(requested_operation).strip().upper()))
        order_time = str(field(raw, "ordertime", "orderTime", "order_time", "time") or "").strip()
        quantity = field(raw, "quantity", "qty")
        quantity = 1 if quantity is None else quantity
        if not 1 <= len(order_id) <= 100:
            raise ValueError("orderid must contain 1–100 characters")
        if not product_id or not name or key(name) not in (key(product_id), key(self.products[product_id]["name"])):
            raise ValueError(f"Unknown or mismatched product: {name or product_ref}")
        if operation is None:
            raise ValueError("operation must be STORE or DELIVER when provided")
        if not order_time:
            raise ValueError("ordertime is required")
        if isinstance(quantity, bool) or not str(quantity).isdigit() or not 1 <= int(quantity) <= 24:
            raise ValueError("quantity must be an integer from 1 to 24")
        return {"orderid":order_id, "productid":product_id,
                "productname":self.products[product_id]["name"], "ordertime":order_time,
                "operation":operation, "quantity":int(quantity)}

    def ingest(self, raw):
        parsed = self.parse_order(raw)
        with self.lock:
            existing = self.orders.get(parsed["orderid"])
            if existing:
                if any(existing[name] != value for name, value in parsed.items()):
                    raise ValueError(f"orderid {parsed['orderid']} already exists with different data")
                return {"orderid":parsed["orderid"], "status":existing["status"], "duplicate":True}
            order = {**parsed, "status":"RECEIVED", "units_completed":0, "active_task":None,
                     "task_ids":[], "reason":"", "assigned_robot":None, "assigned_slot":None}
            self.orders[order["orderid"]] = order
            self.advance_order(order)
            return {"orderid":order["orderid"], "status":order["status"], "duplicate":False}

    def available(self, slot, operation):
        if slot.reserved_by or any(task.state == "QUEUED" and task.requested_slot == slot.id
                                   for task in self.warehouse.tasks.values()):
            return False
        return slot.sku is None if operation == "STORE" else slot.sku is not None

    def advance_order(self, order):
        warehouse = self.warehouse
        if order["active_task"]:
            task = warehouse.tasks[order["active_task"]]
            order["assigned_robot"] = task.robot
            order["assigned_slot"] = task.slot or task.requested_slot
            if task.state == "FAILED":
                order.update(status="FAILED", reason=task.reason or "Robot job failed", active_task=None)
                return
            if task.state != "COMPLETED":
                order.update(status=task.state, reason=task.reason)
                return
            order["units_completed"] += 1
            order["active_task"] = None
            if order["units_completed"] == order["quantity"]:
                order.update(status="COMPLETED", reason="")
                return
        product = self.products[order["productid"]]
        slot_ids = ([f"{product['shelf']}-SRC"] if order["operation"] == "DELIVER" else []) + product["slots"]
        candidates = [warehouse.slots[sid] for sid in slot_ids
                      if self.available(warehouse.slots[sid], order["operation"])]
        if order["operation"] == "DELIVER":
            candidates = [slot for slot in candidates if slot.sku == product["id"]]
        if not candidates:
            order.update(status="WAITING_CAPACITY" if order["operation"] == "STORE" else "WAITING_STOCK",
                         reason="No empty slot in this product shelf group" if order["operation"] == "STORE"
                         else "No stored unit of this product is available")
            return
        slot = candidates[0]
        task_id = (warehouse.request_inbound(product["id"]) if order["operation"] == "STORE"
                   else warehouse.request_outbound(product["id"]))
        warehouse.tasks[task_id].requested_slot = slot.id
        order.update(active_task=task_id, status="QUEUED", reason="", assigned_slot=slot.id,
                     assigned_robot=None)
        order["task_ids"].append(task_id)

    def tick(self):
        with self.lock:
            for order in self.orders.values():
                if order["status"] not in ("COMPLETED", "FAILED"):
                    self.advance_order(order)
            self.warehouse.step(TICK)
            for order in self.orders.values():
                if order["status"] not in ("COMPLETED", "FAILED"):
                    self.advance_order(order)

    def loop(self):
        while self.running:
            start = time.monotonic()
            self.tick()
            time.sleep(max(0.005, TICK / max(self.speed, 0.1) - (time.monotonic() - start)))

    def set_source(self, url, interval=5, bearer_token=None):
        url = str(url or "").strip()
        parsed = urlparse(url)
        if url and (parsed.scheme not in ("http", "https") or not parsed.netloc
                    or parsed.username or parsed.password):
            raise ValueError("Source must be an http(s) URL without embedded credentials")
        interval = float(interval)
        if not 2 <= interval <= 300:
            raise ValueError("Polling interval must be 2–300 seconds")
        with self.lock:
            self.source_url, self.source_interval = url, interval
            if bearer_token is not None:
                self.source_token = str(bearer_token)
            self.source_error = ""
        return {"url":url, "interval_seconds":interval, "enabled":bool(url)}

    def poll_once(self):
        with self.lock:
            url, token = self.source_url, self.source_token
        if not url:
            raise ValueError("Configure an order API URL first")
        request = Request(url, headers={"Accept":"application/json"})
        if token:
            request.add_header("Authorization", f"Bearer {token}")
        try:
            with urlopen(request, timeout=10) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("Order API response exceeds 2 MB")
            payload = json.loads(body)
            records = payload if isinstance(payload, list) else payload.get("orders", [payload])
            if not isinstance(records, list):
                raise ValueError("Order API must return one order, an array, or {\"orders\": [...]}")
            summary = {"accepted":0, "duplicates":0, "rejected":[]}
            for index, record in enumerate(records):
                try:
                    result = self.ingest(record)
                    summary["duplicates" if result["duplicate"] else "accepted"] += 1
                except ValueError as exc:
                    summary["rejected"].append({"index":index, "error":str(exc)})
            with self.lock:
                self.last_poll = time.time()
                self.source_error = f"{len(summary['rejected'])} orders rejected" if summary["rejected"] else ""
            return summary
        except Exception as exc:
            with self.lock:
                self.last_poll, self.source_error = time.time(), str(exc)
            raise

    def poll_loop(self):
        while self.running:
            with self.lock:
                url, interval = self.source_url, self.source_interval
            if url:
                try:
                    self.poll_once()
                except Exception:
                    pass
            time.sleep(interval if url else 1)

    def snapshot(self):
        with self.lock:
            products = []
            for product in self.products.values():
                slots = [self.warehouse.slots[sid] for sid in product["slots"]]
                source = self.warehouse.slots[f"{product['shelf']}-SRC"]
                products.append({**product, "occupied":source.source_units + sum(slot.sku is not None for slot in slots),
                                 "capacity":source.capacity_units + len(slots),
                                 "source_units":source.source_units})
            return {"warehouse":self.warehouse.snapshot(),
                    "orders":[order.copy() for order in self.orders.values()],
                    "products":products,
                    "source":{"url":self.source_url, "enabled":bool(self.source_url),
                              "interval_seconds":self.source_interval, "error":self.source_error,
                              "last_poll":self.last_poll}}
