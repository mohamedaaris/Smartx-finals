"""Estimate task energy using actual graph routes and a charging reserve."""


def estimate_task_energy(graph, robot, task, shelf, energy_per_metre, reserve, conveyor=None):
    destinations = ([robot.node,"PICKUP",shelf,"CHARGE_1"] if task.kind == "INBOUND"
                    else [robot.node,shelf,"PACKING",conveyor or "CONV_2","CHARGE_1"])
    metres = 0
    for a,b in zip(destinations,destinations[1:]):
        path = graph.path(a,b,charge_route=b == "CHARGE_1")
        if not path:
            return float("inf")
        metres += sum(graph.edges[x][y] for x,y in zip(path,path[1:]))
    return metres*energy_per_metre+reserve+1
