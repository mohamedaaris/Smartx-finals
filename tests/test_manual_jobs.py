import unittest

from sim.engine import Warehouse
from sim.geometry import MIN_SEPARATION
from sim.sensors import footprints_overlap


class ManualJobValidation(unittest.TestCase):
    def test_operator_chooses_robot_slot_and_conveyor(self):
        w = Warehouse()
        inbound = w.request_manual("INBOUND", "AMR-01", "AR1-1", "BOX-001")
        w.step()
        task = w.tasks[inbound]
        self.assertEqual((task.robot, task.slot), ("AMR-01", "AR1-1"))
        for _ in range(3000):
            w.step()
            if task.state == "COMPLETED":
                break
        self.assertEqual(task.state, "COMPLETED")
        self.assertEqual(w.slots["AR1-1"].sku, "BOX-001")
        for _ in range(1000):
            if w.robots["AMR-01"].status == "IDLE":
                break
            w.step()
        self.assertEqual(w.robots["AMR-01"].status, "IDLE")
        outbound = w.request_manual("OUTBOUND", "AMR-01", "AR1-1", conveyor="CONV_3")
        for _ in range(4000):
            w.step()
            if w.tasks[outbound].state == "COMPLETED":
                break
        self.assertEqual(w.tasks[outbound].robot, "AMR-01")
        self.assertEqual(w.tasks[outbound].conveyor, "CONV_3")
        self.assertEqual(w.tasks[outbound].state, "COMPLETED")
        self.assertIsNone(w.slots["AR1-1"].sku)

    def test_center_aisle_then_selected_shelf_branch(self):
        w = Warehouse()
        task_id = w.request_manual("INBOUND", "AMR-01", "CR2-1", "CENTER")
        w.step()
        robot = w.robots["AMR-01"]
        self.assertEqual(robot.task_id, task_id)
        robot.node = "PICKUP"
        robot.x, robot.y = w.graph.nodes["PICKUP"].x, w.graph.nodes["PICKUP"].y
        robot.status = "MOVING_TO_SHELF"
        self.assertTrue(w._route(robot, "CR2"))
        self.assertIn("BN", robot.path)
        self.assertIn("B2", robot.path)
        self.assertIn("C2", robot.path)
        self.assertEqual(robot.path[-1], "CR2")

    def test_low_battery_interrupts_and_resumes_same_job(self):
        w = Warehouse()
        task_id = w.request_manual("INBOUND", "AMR-01", "AR1-1", "CHARGE-FIRST")
        w.step()
        robot = w.robots["AMR-01"]
        robot.battery = 30
        w.step()
        self.assertEqual(robot.task_id, task_id)
        self.assertEqual(robot.status, "MOVING_TO_CHARGER")
        self.assertEqual(robot.charge_resume_status, "MOVING_TO_PICKUP")
        for _ in range(6000):
            w.step()
            self.assertGreater(robot.battery, 0)
            if w.tasks[task_id].state == "COMPLETED":
                break
        self.assertEqual(w.tasks[task_id].state, "COMPLETED")
        self.assertTrue(any("returning to" in e["message"] for e in w.events))

    def test_zero_battery_cannot_move(self):
        w = Warehouse()
        task_id = w.request_manual("MOVE", "AMR-01", destination="PICKUP")
        w.step()
        robot = w.robots["AMR-01"]
        robot.battery = 0
        before = (robot.x, robot.y)
        w.step()
        self.assertEqual((robot.x, robot.y), before)
        self.assertEqual(robot.status, "POWER_DEPLETED")
        self.assertEqual(w.tasks[task_id].state, "FAILED")

    def test_move_only_to_chosen_station(self):
        w = Warehouse()
        task_id = w.request_manual("MOVE", "AMR-02", destination="DELIVERY")
        for _ in range(2000):
            w.step()
            if w.tasks[task_id].state == "COMPLETED":
                break
        self.assertEqual(w.tasks[task_id].state, "COMPLETED")
        self.assertEqual(w.robots["AMR-02"].node, "DELIVERY")
        self.assertEqual(w.robots["AMR-02"].status, "IDLE")

    def test_two_manual_jobs_share_center_and_reach_opposite_aisles(self):
        w = Warehouse()
        left = w.request_manual("INBOUND", "AMR-01", "AR1-1", "LEFT")
        right = w.request_manual("INBOUND", "AMR-02", "CR1-1", "RIGHT")
        for _ in range(4000):
            w.step()
            robots = list(w.robots.values())
            self.assertFalse(any(footprints_overlap(a, b) for i, a in enumerate(robots) for b in robots[i + 1:]))
            if all(w.tasks[t].state == "COMPLETED" for t in (left, right)):
                break
        self.assertEqual(w.tasks[left].state, "COMPLETED")
        self.assertEqual(w.tasks[right].state, "COMPLETED")
        self.assertGreaterEqual(w.telemetry.minimum_clearance, MIN_SEPARATION - 0.01)

    def test_sensing_reports_objects_within_five_metres(self):
        w = Warehouse()
        robot = w.robots["AMR-01"]
        close = w.add_obstacle(robot.x + 3, robot.y, "human")
        far = w.add_obstacle(robot.x + 7, robot.y, "debris")
        state = w.snapshot()
        sensed = next(r for r in state["robots"] if r["id"] == robot.id)
        self.assertIn(close, sensed["detected_obstacles"])
        self.assertNotIn(far, sensed["detected_obstacles"])
        self.assertEqual(state["config"]["detection_radius"], 5)


if __name__ == "__main__":
    unittest.main()
