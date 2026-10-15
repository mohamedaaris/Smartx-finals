"""Geometric sensing and obstruction tests; no camera inference or hardware LiDAR."""
from math import dist, cos, sin, pi
from .geometry import ROBOT_LENGTH, ROBOT_WIDTH, SIDE_CLEARANCE


def footprints_overlap(a, b, position=None, heading=None):
    """Separating-axis check of both oriented footprints plus safety clearance."""
    x,y = position or (a.x,a.y)
    theta = a.heading if heading is None else heading
    length = ROBOT_LENGTH/2+SIDE_CLEARANCE
    width = ROBOT_WIDTH/2+SIDE_CLEARANCE
    for axis in (theta,theta+pi/2,b.heading,b.heading+pi/2):
        separation = abs((b.x-x)*cos(axis)+(b.y-y)*sin(axis))
        radius_a = length*abs(cos(axis-theta))+width*abs(sin(axis-theta))
        radius_b = length*abs(cos(axis-b.heading))+width*abs(sin(axis-b.heading))
        if separation >= radius_a+radius_b:
            return False
    return True


def obstructed_nodes(graph, obstacles, clearance=1.8):
    return {name for name,node in graph.nodes.items() for obstacle in obstacles.values()
            if dist((node.x,node.y),(obstacle["x"],obstacle["y"])) < clearance}


def obstructed_edges(graph, obstacles, clearance=1.8):
    blocked = set()
    for a,links in graph.edges.items():
        p = graph.nodes[a]
        for b in links:
            if a > b:
                continue
            q = graph.nodes[b]
            dx,dy = q.x-p.x,q.y-p.y
            for o in obstacles.values():
                t = max(0,min(1,((o["x"]-p.x)*dx+(o["y"]-p.y)*dy)/(dx*dx+dy*dy)))
                if dist((p.x+t*dx,p.y+t*dy),(o["x"],o["y"])) < clearance:
                    blocked.add(tuple(sorted((a,b))))
    return blocked
