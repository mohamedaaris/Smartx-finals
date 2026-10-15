import json
import threading
import unittest
import urllib.error
import urllib.request

from app import Handler, Runtime, SimulationServer


class ControllerApiValidation(unittest.TestCase):
    def setUp(self):
        self.runtime = Runtime(False,1)
        handler = type("ValidationHandler",(Handler,),{"runtime":self.runtime,"log_message":lambda *args:None})
        self.server = SimulationServer(("127.0.0.1",0),handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self,path):
        with urllib.request.urlopen(self.base+path) as response:
            return json.load(response)

    def post(self,path,value):
        request = urllib.request.Request(self.base+"/api/"+path,data=json.dumps(value).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(request) as response:
            return json.load(response)

    def test_paused_empty_start_and_no_demo_reset(self):
        state = self.get("/api/state")
        self.assertTrue(state["paused"])
        self.assertEqual(state["time"],0)
        self.assertEqual(state["tasks"],[])
        self.post("reset",{"demo":True})
        self.assertEqual(self.get("/api/state")["packages"],[])

    def test_operator_workflow_and_measured_report(self):
        created = self.post("batch",{"prefix":"API-RUN","count":5,"retrieve":True})
        self.assertEqual(len(created["tasks"]),10)
        self.post("control",{"step":True})
        report = self.get("/api/report")
        self.assertEqual(len(report["tasks"]),10)
        self.assertEqual(report["time"],.1)
        self.assertEqual(len(report["history"]),1)
        self.assertEqual(report["metrics"]["completed"],0)
        self.assertFalse(any(s["sku"] for s in report["slots"]))

    def test_manual_job_preserves_operator_choices(self):
        created = self.post("manual-job", {"kind": "INBOUND", "robot_id": "AMR-01",
                                           "slot_id": "AR1-1", "sku": "MANUAL-001"})
        self.post("control", {"step": True})
        task = next(t for t in self.get("/api/state")["tasks"] if t["id"] == created["task_id"])
        self.assertEqual(task["robot"], "AMR-01")
        self.assertEqual(task["slot"], "AR1-1")
        self.assertEqual(task["sku"], "MANUAL-001")

    def test_local_rendering_dependency_is_served(self):
        with urllib.request.urlopen(self.base+"/vendor/build/three.module.js") as response:
            self.assertEqual(response.status,200)
            self.assertIn("javascript",response.headers["Content-Type"])

    def test_add_robot_respects_charging_capacity(self):
        added = [self.post("add-robot", {}) for _ in range(3)]
        self.assertEqual([r["robot_id"] for r in added], ["AMR-06", "AMR-07", "AMR-08"])
        state = self.get("/api/state")
        self.assertEqual(state["charging_capacity"], 8)
        self.assertEqual(len({r["node"] for r in state["robots"]}), 8)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.post("add-robot", {})
        self.assertEqual(error.exception.code, 400)


class RunLifecycleValidation(unittest.TestCase):
    def test_auto_pause_after_delivered_package_and_idle_fleet(self):
        runtime = Runtime(False,1)
        runtime.warehouse.request_inbound("LIFECYCLE")
        runtime.warehouse.request_outbound("LIFECYCLE")
        runtime.paused = False
        for _ in range(3000):
            runtime.advance()
            if runtime.paused:
                break
        self.assertTrue(runtime.paused)
        self.assertEqual(runtime.warehouse.telemetry.metrics(runtime.warehouse)["delivered"],1)
        self.assertTrue(all(r.status == "IDLE" for r in runtime.warehouse.robots.values()))
        elapsed = runtime.warehouse.time
        runtime.advance()
        self.assertEqual(runtime.warehouse.time,elapsed)

    def test_auto_pause_after_all_charging_finishes(self):
        from sim.engine import Warehouse
        runtime = Runtime(False,1)
        runtime.warehouse = Warehouse(initial_battery=20)
        runtime.paused = False
        for _ in range(6000):
            runtime.advance()
            if runtime.paused:
                break
        self.assertTrue(runtime.paused)
        self.assertTrue(all(r.battery > 25 and r.status == "IDLE" for r in runtime.warehouse.robots.values()))
        self.assertEqual(runtime.warehouse.charge_locks,{})


if __name__ == "__main__":
    unittest.main()
