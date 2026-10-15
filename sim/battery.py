"""Estimate task energy using actual graph routes and a charging reserve."""


def estimate_task_energy(graph, robot, task, shelf, energy_per_metre, reserve, conveyor=None):
    home = f"DEPOT_{int(robot.id[-2:])}"
    destinations = ([robot.node,"PICKUP",shelf,home] if task.kind == "INBOUND"
                    else [robot.node,shelf,"PACKING",conveyor or "CONV_2",home])
    metres = 0
    for a,b in zip(destinations,destinations[1:]):
        path = graph.path(a,b,charge_route=b == home)
        if not path:
            return float("inf")
        metres += sum(graph.edges[x][y] for x,y in zip(path,path[1:]))
    return metres*energy_per_metre+reserve+1
