"""Measurements sampled from executed simulation steps."""
from math import dist


class Telemetry:
    def __init__(self):
        self.samples = []
        self.minimum_clearance = None
        self.next_sample = 0

    def observe(self, warehouse):
        robots = list(warehouse.robots.values())
        clearance = min(dist((a.x, a.y), (b.x, b.y))
                        for i, a in enumerate(robots) for b in robots[i + 1:])
        self.minimum_clearance = clearance if self.minimum_clearance is None else min(self.minimum_clearance, clearance)
        if warehouse.time + 1e-8 < self.next_sample:
            return
        self.next_sample = warehouse.time + 1
        self.samples.append({"time": round(warehouse.time, 2),
            "active": sum(bool(r.task_id) for r in robots),
            "blocked": sum(bool(r.block_reason) for r in robots),
            "completed": sum(t.state == "COMPLETED" for t in warehouse.tasks.values()),
            "stored": sum(s.source_units if s.source_backed else bool(s.package_id)
                          for s in warehouse.slots.values()),
            "distance": round(sum(r.distance_m for r in robots), 2),
            "battery": [round(r.battery, 2) for r in robots]})
        self.samples = self.samples[-3600:]

    def metrics(self, warehouse):
        completed = [t for t in warehouse.tasks.values() if t.state == "COMPLETED"]
        return {"completed": len(completed), "distance_m": round(sum(r.distance_m for r in warehouse.robots.values()), 2),
            "mean_task_seconds": round(sum(t.completed-t.created for t in completed) / len(completed), 2) if completed else None,
            "throughput_per_hour": round(len(completed)*3600/warehouse.time, 2) if warehouse.time and completed else None,
            "minimum_clearance_m": round(self.minimum_clearance, 3) if self.minimum_clearance is not None else None,
            "delivered": sum(p["stage"] == "DELIVERED" for p in warehouse.packages.values()),
            "waiting_seconds": round(sum(r.waiting_seconds for r in warehouse.robots.values()), 2)}
