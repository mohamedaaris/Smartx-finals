"""Slot construction and inventory eligibility rules for the central controller."""
from .models import Slot


def create_slots(graph):
    slots = {}
    for shelf in (f"{col}R{i}" for col in "ABC" for i in range(1,5)):
        for number in (1,2):
            sid = f"{shelf}-{number}"
            position = graph.model.get("slots",{}).get(sid,{}).get("position")
            slots[sid] = Slot(sid,shelf,position=position)
    return slots


def eligible_slots(task, slots, shelf_locks):
    if task.kind == "INBOUND":
        candidates = [s for s in slots.values() if s.sku is None and s.reserved_by is None and s.shelf not in shelf_locks]
        return candidates, "No free, unlocked shelf slot" if not candidates else ""
    stock = [s for s in slots.values() if s.sku == task.sku]
    if not stock:
        return [], "Requested SKU is not in inventory"
    candidates = [s for s in stock if s.shelf not in shelf_locks and s.reserved_by is None]
    return candidates, "Shelf locked by another task" if not candidates else ""
