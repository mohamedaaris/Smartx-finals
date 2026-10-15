import json
import threading
import unittest
import urllib.request
from collections import Counter

from app import Handler, Runtime, SimulationServer
from automation import AutomationRuntime, DEFAULT_SOURCE_URL
from scripts.inspect_source_stock import source_cartons


class AutomationWorkflowTests(unittest.TestCase):
    def test_catalog_and_store_delivery_flow_are_isolated(self):
        auto = AutomationRuntime()
        manual = Runtime(False, 1)
        slots = [slot for product in auto.products.values() for slot in product["slots"]]
        self.assertEqual((len(auto.products), len(slots), len(set(slots))), (12, 24, 24))
        cartons = source_cartons()
        self.assertEqual(len(cartons), 858)
        self.assertEqual(Counter(c["shelf"] for c in cartons), {
            f"{col}R{row}": count for col in "ABC"
            for row, count in ((1, 81), (2, 82), (3, 82), (4, 41))})
        self.assertEqual(sum(s.source_units for s in auto.warehouse.slots.values()), 858)
        inbound = {"orderid":"IN-1", "productname":"TV", "ordertime":"2026-10-15T12:00:00+05:30", "operation":"STORE"}
        self.assertEqual(auto.ingest(inbound)["status"], "QUEUED")
        self.assertTrue(auto.ingest(inbound)["duplicate"])
        for _ in range(3500):
            auto.tick()
            if auto.orders["IN-1"]["status"] == "COMPLETED":
                break
        stored = auto.orders["IN-1"]
        self.assertEqual(stored["status"], "COMPLETED")
        self.assertIn(stored["assigned_slot"], auto.products["tv"]["slots"])
        self.assertTrue(stored["assigned_robot"])
        outbound = {"orderid":"OUT-1", "productname":"TV", "ordertime":"2026-10-15T12:05:00+05:30", "operation":"DELIVER"}
        self.assertEqual(auto.ingest(outbound)["status"], "QUEUED")
        for _ in range(5000):
            auto.tick()
            if auto.orders["OUT-1"]["status"] == "COMPLETED":
                break
        self.assertEqual(auto.orders["OUT-1"]["status"], "COMPLETED")
        self.assertEqual(auto.orders["OUT-1"]["assigned_slot"], "AR2-SRC")
        self.assertEqual(auto.warehouse.slots["AR2-SRC"].source_units, 81)
        self.assertEqual(auto.warehouse.slots[stored["assigned_slot"]].sku, "tv")
        self.assertEqual(manual.warehouse.tasks, {})

    def test_missing_stock_waits_and_conflicting_order_id_rejects(self):
        auto = AutomationRuntime()
        source = auto.warehouse.slots["BR1-SRC"]
        source.sku = source.package_id = None
        source.source_units = 0
        auto.warehouse.source_stock["BR1"] = []
        order = {"orderid":"WAIT-1", "productname":"Sofa", "ordertime":"2026-10-15T12:00:00+05:30", "operation":"DELIVER"}
        self.assertEqual(auto.ingest(order)["status"], "WAITING_STOCK")
        with self.assertRaises(ValueError):
            auto.ingest({**order, "operation":"STORE"})


class AutomationApiTests(unittest.TestCase):
    def setUp(self):
        self.auto = AutomationRuntime()
        def get(handler):
            if handler.path == "/test-feed":
                handler._json({"orders":[{"orderid":"FEED-1", "productname":"Drone",
                    "ordertime":"2026-10-15T12:00:00+05:30", "operation":"STORE"}]})
            elif handler.path == "/test-company-feed":
                handler._json({"status":"online", "totalOrders":2,
                    "latestOrder":{"orderid":"LIVE-2", "product":"Oven",
                                   "time":"2026-10-15T09:19:54.626Z"},
                    "orders":[{"orderid":"LIVE-1", "product":"Table Fan",
                               "time":"2026-10-15T09:19:45.320Z"},
                              {"orderid":"LIVE-2", "product":"Oven",
                               "time":"2026-10-15T09:19:54.626Z"}]})
            else:
                Handler.do_GET(handler)
        handler = type("AutomationTestHandler", (Handler,), {"runtime":Runtime(False,1),
            "automation":self.auto, "do_GET":get, "log_message":lambda *args:None})
        self.server = SimulationServer(("127.0.0.1",0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_route_order_api_and_feed_deduplication(self):
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertIn(b'href="/automation"', response.read())
        with urllib.request.urlopen(self.base + "/automation") as response:
            page = response.read()
            self.assertIn(b"3D warehouse", page)
            self.assertIn(b"/automation.js", page)
        with urllib.request.urlopen(self.base + "/automation.js") as response:
            script = response.read()
            self.assertIn(b"WarehouseView", script)
            self.assertIn(b"/api/automation/state", script)
        order = {"orderid":"API-1", "productname":"Chair", "ordertime":"2026-10-15T12:00:00+05:30", "operation":"STORE"}
        request = urllib.request.Request(self.base + "/api/automation/orders", data=json.dumps(order).encode(), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 202)
            self.assertEqual(json.load(response)["orderid"], "API-1")
        with urllib.request.urlopen(self.base + "/api/automation/orders/API-1") as response:
            self.assertEqual(json.load(response)["assigned_slot"], "CR2-1")
        self.auto.set_source(self.base + "/test-feed")
        self.assertEqual(self.auto.poll_once()["accepted"], 1)
        self.assertEqual(self.auto.poll_once()["duplicates"], 1)
        self.assertEqual(len(self.auto.orders), 2)

    def test_company_feed_defaults_to_delivery_and_deduplicates(self):
        self.assertEqual(self.auto.source_url, DEFAULT_SOURCE_URL)
        self.auto.set_source(self.base + "/test-company-feed")
        self.assertEqual(self.auto.poll_once(), {"accepted":2, "duplicates":0, "rejected":[]})
        self.assertEqual(self.auto.poll_once(), {"accepted":0, "duplicates":2, "rejected":[]})
        self.assertEqual(len(self.auto.orders), 2)
        for order in self.auto.orders.values():
            self.assertEqual(order["operation"], "DELIVER")
            self.assertEqual(order["status"], "QUEUED")
            self.assertIn(order["assigned_slot"], ("BR3-SRC", "BR4-SRC"))


if __name__ == "__main__":
    unittest.main()
