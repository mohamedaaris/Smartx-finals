"""Structured controller records shared by inventory, traffic and rendering."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class Slot:
    id: str
    shelf: str
    sku: str | None = None
    package_id: str | None = None
    reserved_by: str | None = None
    position: list[float] | None = None
    source_board: str | None = None
    validated_vacant: bool = False
    capacity_units: int = 1
    package_dimensions: list[float] | None = None
    max_weight_kg: float | None = None


@dataclass
class Task:
    id: str
    kind: str
    sku: str
    created: float
    state: str = "QUEUED"
    assigned: float | None = None
    completed: float | None = None
    robot: str | None = None
    slot: str | None = None
    reason: str = ""
    package_id: str | None = None
    conveyor: str | None = None
    packed: float | None = None
    deposited: float | None = None
    final_battery: float | None = None
    final_location: str | None = None
    requested_robot: str | None = None
    requested_slot: str | None = None
    requested_conveyor: str | None = None
    destination: str | None = None


@dataclass
class Robot:
    id: str
    source_object: str
    node: str
    x: float
    y: float
    battery: float
    depot_slot: str | None = None
    heading: float = 0.0
    status: str = "IDLE"
    task_id: str | None = None
    target: str | None = None
    path: list[str] = field(default_factory=list)
    route_index: int = 0
    carrying: bool = False
    hold_until: float = 0.0
    blocked_since: float = 0.0
    block_reason: str = ""
    edge: tuple[str, str] | None = None
    shelf_to_release: str | None = None
    conveyor_to_release: str | None = None
    charge_bay: str | None = None
    yield_junction: str | None = None
    distance_m: float = 0.0
    waiting_seconds: float = 0.0
    moving_seconds: float = 0.0
    velocity: float = 0.0
    action_started: float = 0.0
    resume_target: str | None = None
    resume_status: str | None = None
    yield_edge: tuple[str, str] | None = None
    waiting_reserved: str | None = None
    pending_target: str | None = None
    pending_avoid: set[str] = field(default_factory=set)
    charge_resume_status: str | None = None
    charge_resume_target: str | None = None
    last_conflict_log: float = -100.0
    last_conflict_reason: str = ""


