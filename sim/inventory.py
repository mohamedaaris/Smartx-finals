"""Slot construction and inventory eligibility rules for the central controller."""
from .models import Slot


def create_slots(graph):
    slots = {}
    source_slots = graph.model.get("slots", {})
    package_dimensions = graph.model.get("slot_validation", {}).get("package_dimensions")
    for shelf in (f"{col}R{i}" for col in "ABC" for i in range(1,5)):
        for number in (1,2):
            sid = f"{shelf}-{number}"
            source = source_slots.get(sid, {})
            slots[sid] = Slot(sid, shelf, position=source.get("position"),
                              source_board=source.get("source_board"),
                              validated_vacant=bool(source.get("validated_vacant")),
                              package_dimensions=package_dimensions)
    return slots


def eligible_slots(task, slots, shelf_locks):
    if task.kind == "INBOUND":
        candidates = [s for s in slots.values() if s.validated_vacant and s.sku is None and s.reserved_by is None and s.shelf not in shelf_locks]
        return candidates, "No free, unlocked shelf slot" if not candidates else ""
    stock = [s for s in slots.values() if s.sku == task.sku]
    if not stock:
        return [], "Requested SKU is not in inventory"
    candidates = [s for s in stock if s.shelf not in shelf_locks and s.reserved_by is None]
    return candidates, "Shelf locked by another task" if not candidates else ""
