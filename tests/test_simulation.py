import unittest
from math import dist

from sim.engine import Warehouse
from sim.geometry import AISLES, MIN_SEPARATION, THREE_LANE_FEASIBLE, THREE_LANE_REQUIRED_WIDTH
from sim.sensors import footprints_overlap


class WarehouseScenarios(unittest.TestCase):
    def test_a_and_l_five_robot_end_to_end(self):
        w = Warehouse(demo=True)
        first = w.slots["AR1-1"].package_id
        least_clearance = float("inf")
        # Packing, proximity speed reduction and conveyor transport are timed
        # operations; the shared-depot workflow has a 350 s deadline.
        for _ in range(3500):
            w.step()
            robots = list(w.robots.values())
            for i, robot in enumerate(robots):
                for other in robots[i + 1:]:
                    least_clearance = min(least_clearance,
                                          dist((robot.x, robot.y), (other.x, other.y)))
            if all(t.state == "COMPLETED" for t in w.tasks.values()):
                break
        self.assertTrue(all(t.state == "COMPLETED" for t in w.tasks.values()))
        self.assertGreaterEqual(least_clearance, MIN_SEPARATION - .01)
        self.assertEqual(w.shelf_locks, {})
        self.assertEqual(w.conveyor_locks, {})
        self.assertNotEqual(w.slots["AR1-1"].package_id, first)
        self.assertEqual(len(w.robots), 5)

    def test_b_full_shelves_queue_inbound_and_reassign_pickup_robot(self):
        w = Warehouse(fixture=True)
        for slot in w.slots.values():
            slot.sku = "FULL"
            slot.package_id = "PRELOADED"
        for rid in ("AMR-03", "AMR-04", "AMR-05"):
            w.robots[rid].battery = 20
        inbound = w.request_inbound("NEW")
        outbound = w.request_outbound("FULL")
        w.step()
        self.assertEqual(w.tasks[inbound].state, "QUEUED")
        self.assertIn(w.tasks[outbound].robot, ("AMR-01", "AMR-02"))

    def test_c_same_shelf_has_one_owner(self):
        w = Warehouse(fixture=True)
        a = w.request_outbound("SKU-01")
        b = w.request_outbound("SKU-01")
        w.step()
        self.assertEqual(w.tasks[a].state, "ASSIGNED")
        self.assertEqual(w.tasks[b].state, "QUEUED")
        self.assertEqual(w.shelf_locks["AR1"], a)

    def test_d_independent_shelves_progress_together(self):
        w = Warehouse(fixture=True)
        a = w.request_outbound("SKU-01")
        b = w.request_outbound("SKU-05")
        w.step()
        self.assertEqual(w.tasks[a].state, "ASSIGNED")
        self.assertEqual(w.tasks[b].state, "ASSIGNED")
        self.assertNotEqual(w.tasks[a].robot, w.tasks[b].robot)

    def test_e_measured_three_lanes_do_not_fit(self):
        self.assertFalse(THREE_LANE_FEASIBLE)
        self.assertGreaterEqual(AISLES["west"][1] - AISLES["west"][0],
                                THREE_LANE_REQUIRED_WIDTH)
        self.assertLess(AISLES["east"][1] - AISLES["east"][0],
                        THREE_LANE_REQUIRED_WIDTH)

    def test_f_conveyor_lanes_exclusive(self):
        w = Warehouse(demo=True)
        seen_parallel = False
        for _ in range(1000):
            w.step()
            owners = list(w.conveyor_locks.values())
            self.assertEqual(len(owners), len(set(owners)))
            seen_parallel |= len(owners) > 1
        self.assertTrue(seen_parallel)

    def test_g_four_robot_priority(self):
        w = Warehouse(fixture=True)
        a, b, c, d = [w.robots[f"AMR-{i:02d}"] for i in range(1, 5)]
        a.battery = 8
        b.carrying = True
        c.task_id = w.request_inbound("NEW")
        w.tasks[c.task_id].assigned = 1
        d.task_id = w.request_inbound("NEW2")
        w.tasks[d.task_id].assigned = 2
        self.assertEqual([r.id for r in sorted((a, b, c, d), key=w._priority)],
                         [a.id, b.id, c.id, d.id])

    def test_g_four_robot_junction_clears(self):
        w = Warehouse(fixture=True)
        setup = [
            ("AMR-01", "A2", "C2"),
            ("AMR-02", "C2", "A2"),
            ("AMR-03", "BR2", "BR3"),
            ("AMR-04", "BR3", "BR2"),
        ]
        for rid, start, goal in setup:
            r = w.robots[rid]
            p = w.graph.nodes[start]
            r.node, r.x, r.y = start, p.x, p.y
            r.status = "MOVING_TO_RETRIEVAL"
            w._route(r, goal)
        r = w.robots["AMR-05"]
        p = w.graph.nodes["CHARGE_1"]
        r.node, r.x, r.y, r.status = "CHARGE_1", p.x, p.y, "CHARGING"
        r.charge_bay = "CHARGE_1"
        w.charge_locks["CHARGE_1"] = r.id
        least_clearance = float("inf")
        for _ in range(3000):
            w.step()
            robots = list(w.robots.values())[:4]
            for i, robot in enumerate(robots):
                for other in robots[i+1:]:
                    least_clearance = min(least_clearance,
                                          dist((robot.x, robot.y), (other.x, other.y)))
            if all(w.robots[rid].node == goal for rid, _, goal in setup):
                break
        self.assertGreaterEqual(least_clearance, MIN_SEPARATION - .01)
        self.assertTrue(all(w.robots[rid].node == goal for rid, _, goal in setup))

    def test_h_obstacle_is_reported_and_blocks_node(self):
        w = Warehouse(fixture=True)
        p = w.graph.nodes["AN"]
        oid = w.add_obstacle(p.x, p.y, "human")
        task = w.request_inbound("OBSTACLE-TEST")
        self.assertIn("AN", w._obstructed_nodes())
        self.assertEqual(w.snapshot()["obstacles"][0]["category"], "human")
        w.run(120)
        self.assertEqual(w.tasks[task].state, "COMPLETED")
        self.assertNotEqual(w.robots[w.tasks[task].robot].node, "AN")
        self.assertFalse(w.shelf_locks)
        w.remove_obstacle(oid)
        self.assertNotIn("AN", w._obstructed_nodes())

    def test_i_low_battery_routes_to_own_depot_charger(self):
        w = Warehouse(fixture=True)
        r = w.robots["AMR-01"]
        r.battery = 20
        w.step()
        self.assertEqual(r.status, "MOVING_TO_CHARGER")
        self.assertIn(r.target, w.depot_ids)
        self.assertEqual(w.tasks, {})
        w.run(180)
        self.assertEqual(r.status, "IDLE")
        self.assertIn(r.node, w.depot_ids)
        self.assertGreater(r.battery, 25)
        self.assertEqual(w.charge_locks, {})

    def test_j_extended_depot_charging_is_independent(self):
        w = Warehouse(fixture=True)
        w.charge_locks = {"CHARGE_1": "AMR-01", "CHARGE_2": "AMR-02"}
        r = w.robots["AMR-03"]
        r.battery = 20
        w.step()
        self.assertEqual(r.status, "MOVING_TO_CHARGER")
        self.assertIn(r.target, w.depot_ids)
        self.assertEqual(w.charge_locks[r.target], r.id)

    def test_k_queue_order_after_resource_unlock(self):
        w = Warehouse(fixture=True)
        first = w.request_outbound("SKU-01")
        second = w.request_outbound("SKU-01")
        w.step()
        third = w.request_outbound("SKU-01")
        self.assertEqual(w.tasks[second].state, "QUEUED")
        self.assertEqual(w.tasks[third].state, "QUEUED")
        self.assertEqual(w.shelf_locks["AR1"], first)

    def test_empty_start_has_no_invented_work_or_stock(self):
        w = Warehouse()
        s = w.snapshot()
        self.assertEqual(s["tasks"], [])
        self.assertEqual(s["packages"], [])
        self.assertFalse(any(slot["sku"] for slot in s["slots"]))
        self.assertEqual(s["history"], [])
        self.assertEqual(s["metrics"]["distance_m"], 0)
        self.assertIsNone(s["metrics"]["throughput_per_hour"])

    def test_real_cycle_from_empty_inventory(self):
        w = Warehouse()
        for i in range(5):
            w.request_inbound(f"RUN-{i}")
            w.request_outbound(f"RUN-{i}")
        packed = False
        in_transit = False
        active_robots = set()
        minimum = float("inf")
        for _ in range(6000):
            w.step()
            packed |= any(r.status == "PACKING_PACKAGE" for r in w.robots.values())
            in_transit |= any(t.state == "IN_TRANSIT" for t in w.tasks.values())
            active_robots.update(r.id for r in w.robots.values() if r.task_id)
            minimum = min(minimum, w.telemetry.minimum_clearance)
            robots = list(w.robots.values())
            self.assertFalse(any(footprints_overlap(a,b) for i,a in enumerate(robots) for b in robots[i+1:]))
            if all(t.state == "COMPLETED" for t in w.tasks.values()):
                break
        self.assertEqual(len(active_robots), 5)
        self.assertTrue(packed)
        self.assertTrue(in_transit)
        self.assertTrue(all(t.state == "COMPLETED" for t in w.tasks.values()))
        self.assertEqual(w.telemetry.metrics(w)["delivered"], 5)
        self.assertTrue(all(p["stage"] == "DELIVERED" for p in w.packages.values()))
        self.assertFalse(any(s.package_id for s in w.slots.values()))
        self.assertGreaterEqual(minimum, MIN_SEPARATION-.01)
        self.assertTrue(all(t.packed is not None and t.completed >= t.packed for t in w.tasks.values() if t.kind == "OUTBOUND"))
        self.assertEqual(w.conveyor_locks, {})

    def test_obstacle_between_waypoints_blocks_entire_edge(self):
        w = Warehouse()
        a, b = w.graph.nodes["L1"], w.graph.nodes["L2"]
        w.add_obstacle(a.x, (a.y+b.y)/2, "human")
        key = w._edge_key(a.id, b.id)
        self.assertIn(key, w._obstructed_edges())
        path = w.graph.path(a.id, b.id, blocked_edges=w._obstructed_edges())
        self.assertTrue(path)
        self.assertNotIn(key, [w._edge_key(x,y) for x,y in zip(path,path[1:])])

    def test_conveyor_does_not_complete_order_at_deposit(self):
        w = Warehouse()
        w.request_inbound("DELIVERY-CHECK")
        outbound = w.request_outbound("DELIVERY-CHECK")
        for _ in range(3000):
            w.step()
            if w.conveyor_packages:
                break
        self.assertTrue(w.conveyor_packages)
        snapshot = w.snapshot()
        original_progress = snapshot["conveyor_packages"][0]["progress"]
        w.step()
        self.assertEqual(snapshot["conveyor_packages"][0]["progress"],original_progress)
        self.assertNotEqual(w.tasks[outbound].state, "COMPLETED")
        self.assertIsNone(w.tasks[outbound].completed)
        w.run(80)
        self.assertEqual(w.tasks[outbound].state, "COMPLETED")
        self.assertEqual(w.packages[w.tasks[outbound].package_id]["stage"], "DELIVERED")

    def test_all_five_low_battery_robots_recharge_at_their_depots(self):
        w = Warehouse(initial_battery=20)
        charged = set()
        for _ in range(6000):
            w.step()
            charged.update(r.id for r in w.robots.values() if w._actively_charging(r))
            self.assertLessEqual(len(w.charge_locks), 5)
            self.assertTrue(all(r.battery > 0 for r in w.robots.values()))
            if len(charged) == 5 and all(r.status == "IDLE" and r.battery >= 100
                                         for r in w.robots.values()):
                break
        self.assertEqual(len(charged), 5)
        self.assertTrue(all(r.battery > 25 for r in w.robots.values()))
        self.assertTrue(all(r.status == "IDLE" for r in w.robots.values()))
        self.assertTrue(all(w._in_charging_area(r) for r in w.robots.values()))
        self.assertGreaterEqual(w.telemetry.minimum_clearance, MIN_SEPARATION-.01)
        self.assertEqual(w.charge_locks, {})

    def test_oriented_footprint_blocks_diagonal_corner_contact(self):
        from math import pi
        w = Warehouse()
        a,b = list(w.robots.values())[:2]
        a.x,a.y,a.heading = 0,0,pi/4
        b.x,b.y,b.heading = 2.4,0,-pi/4
        self.assertGreater(dist((a.x,a.y),(b.x,b.y)),MIN_SEPARATION)
        self.assertTrue(footprints_overlap(a,b))
        b.x = 3.1
        self.assertFalse(footprints_overlap(a,b))

    def test_orders_arrive_while_fleet_finishes_charging(self):
        w = Warehouse(initial_battery=20)
        w.run(167)
        for i in range(5):
            w.request_inbound(f"MIX-{i}")
            w.request_outbound(f"MIX-{i}")
        for _ in range(6000):
            w.step()
            self.assertTrue(all(r.battery > 0 for r in w.robots.values()))
            if all(t.state == "COMPLETED" for t in w.tasks.values()):
                break
        self.assertTrue(all(t.state == "COMPLETED" for t in w.tasks.values()))
        self.assertEqual(w.telemetry.metrics(w)["delivered"],5)

    def test_orphaned_edge_released_only_after_owner_clears(self):
        w = Warehouse()
        key = w._edge_key("BS","PARK_E")
        owner = w.robots["AMR-05"]
        owner.node = "BS"
        owner.x,owner.y = w.graph.nodes["BS"].x,w.graph.nodes["BS"].y
        w.edge_locks[key] = owner.id
        w.step()
        self.assertIn(key,w.edge_locks)
        owner.node = "PARK_C"
        owner.x,owner.y = w.graph.nodes["PARK_C"].x,w.graph.nodes["PARK_C"].y
        w.step()
        self.assertNotEqual(w.edge_locks.get(key), owner.id)

    def test_depot_bound_robot_accepts_new_work_above_thirty_percent(self):
        w = Warehouse()
        robot = w.robots["AMR-01"]
        start = w.graph.nodes["PARK_A2"]
        robot.node, robot.x, robot.y = start.id, start.x, start.y
        w.step()
        self.assertEqual(robot.status, "MOVING_TO_DEPOT")
        robot.battery = 31
        task = w.request_manual("MOVE", robot.id, destination="PICKUP")
        w.step()
        self.assertEqual(w.tasks[task].state, "ASSIGNED")
        self.assertEqual(robot.status, "MOVING_TO_DESTINATION")
        self.assertEqual(robot.target, "PICKUP")
        w.run(180)
        self.assertEqual(w.tasks[task].state, "COMPLETED")
        self.assertIn(robot.node, w.depot_ids)

    def test_depot_bound_robot_at_thirty_percent_charges_first(self):
        w = Warehouse()
        robot = w.robots["AMR-01"]
        start = w.graph.nodes["PARK_A2"]
        robot.node, robot.x, robot.y = start.id, start.x, start.y
        w.step()
        robot.battery = 30
        with self.assertRaises(ValueError):
            w.request_manual("MOVE", robot.id, destination="PICKUP")
        w.step()
        self.assertIn(robot.target, w.depot_ids)
        self.assertEqual(robot.status, "MOVING_TO_CHARGER")

    def test_idle_robot_charges_anywhere_in_extended_area(self):
        w = Warehouse()
        robot = w.robots["AMR-01"]
        robot.x, robot.y, robot.battery = -10, -48, 50
        self.assertTrue(w._in_charging_area(robot))
        w.step()
        self.assertGreater(robot.battery, 50)
        self.assertEqual(robot.status, "IDLE")
        self.assertIsNone(robot.target)
        w.run(33)
        self.assertEqual(robot.battery, 100)
        self.assertEqual((robot.x, robot.y), (-10, -48))

    def test_idle_depot_robot_keeps_charging_and_remains_available(self):
        w = Warehouse()
        w.run(160)
        robot = w.robots["AMR-01"]
        self.assertEqual(robot.node, "DEPOT_1")
        robot.battery = 60
        w.run(10)
        self.assertEqual(robot.status, "IDLE")
        self.assertGreater(robot.battery, 60)
        self.assertTrue(w.snapshot()["robots"][0]["charging"])
        w.run(20)
        self.assertEqual(robot.battery, 100)
        self.assertFalse(w.snapshot()["robots"][0]["charging"])

    def test_runtime_waits_for_idle_depot_top_up_before_auto_pause(self):
        from app import Runtime
        runtime = Runtime(False, 1)
        runtime.warehouse.run(160)
        robot = runtime.warehouse.robots["AMR-01"]
        robot.battery = 80
        runtime.paused = False
        runtime.had_activity = True
        for _ in range(200):
            runtime.advance()
            if runtime.paused:
                break
        self.assertEqual(robot.battery, 100)
        self.assertTrue(runtime.paused)

    def test_runtime_returns_last_completed_job_robot_before_pausing(self):
        from app import Runtime
        runtime = Runtime(False, 1)
        task = runtime.warehouse.request_manual("MOVE", "AMR-01", destination="PICKUP")
        runtime.paused = False
        for _ in range(4000):
            runtime.advance()
            if runtime.paused:
                break
        robot = runtime.warehouse.robots["AMR-01"]
        self.assertEqual(runtime.warehouse.tasks[task].state, "COMPLETED")
        self.assertTrue(runtime.warehouse._in_charging_area(robot))
        self.assertTrue(runtime.paused)

    def test_eight_unique_charging_slots_limit_fleet(self):
        w = Warehouse()
        self.assertEqual(len(w.depot_ids), 8)
        self.assertTrue(all(w._in_charging_area(r) and r.node in w.depot_ids
                            for r in w.robots.values()))
        added = [w.add_robot() for _ in range(3)]
        self.assertEqual([r.id for r in added], ["AMR-06", "AMR-07", "AMR-08"])
        self.assertEqual(len({r.node for r in w.robots.values()}), 8)
        self.assertEqual(w.snapshot()["available_charging_slots"], [])
        with self.assertRaisesRegex(ValueError, "Fleet is full"):
            w.add_robot()

    def test_robot_can_use_another_robots_free_slot(self):
        w = Warehouse()
        robot = w.robots["AMR-01"]
        point = w.graph.nodes["PICKUP"]
        robot.node, robot.x, robot.y = point.id, point.x, point.y
        newcomer = w.add_robot()
        self.assertEqual(newcomer.node, "DEPOT_1")
        w.run(160)
        self.assertIn(robot.node, w.depot_ids)
        self.assertNotEqual(robot.node, newcomer.node)
        self.assertEqual(len({r.node for r in w.robots.values()}), len(w.robots))

    def test_imminent_robot_conflict_records_decision(self):
        w = Warehouse(fixture=True)
        robot = w.robots["AMR-01"]
        w._set_wait(robot, "Imminent collision with AMR-02; holding while a safe reroute is evaluated")
        self.assertTrue(any("Imminent collision with AMR-02" in e["message"]
                            for e in w.snapshot()["events"]))


if __name__ == "__main__":
    unittest.main()
