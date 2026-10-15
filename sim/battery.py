"""Estimate task energy using actual graph routes and a charging reserve."""


def estimate_task_energy(graph, robot, task, shelf, energy_per_metre, reserve, conveyor=None):
    destinations = ([robot.node,"PICKUP",shelf] if task.kind == "INBOUND"
                    else [robot.node,shelf,"PACKING",conveyor or "CONV_2"])
    metres = 0
    for a,b in zip(destinations,destinations[1:]):
        path = graph.path(a,b)
        if not path:
            return float("inf")
        metres += sum(graph.edges[x][y] for x,y in zip(path,path[1:]))
    returns = []
    for home, point in graph.nodes.items():
        if point.kind != "depot":
            continue
        path = graph.path(destinations[-1],home,charge_route=True)
        if path:
            returns.append(sum(graph.edges[x][y] for x,y in zip(path,path[1:])))
    return (metres + max(returns))*energy_per_metre+reserve+1 if returns else float("inf")
