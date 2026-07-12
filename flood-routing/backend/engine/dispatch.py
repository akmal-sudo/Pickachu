"""
Phase 3 — Fleet dispatch.

Given N vehicle locations and M victim locations, finds the assignment of
vehicles to victims that minimizes TOTAL response time across the whole
fleet — not just "send the nearest vehicle to each victim" (which can be
badly suboptimal once multiple victims are involved).

Uses the Hungarian algorithm (scipy.optimize.linear_sum_assignment), which
solves this exactly and fast. Cost matrix entries come straight from the
same RoutingEngine.shortest_path() used everywhere else, so dispatch
automatically respects any active flood state — a flooded road makes that
path more expensive, so the optimizer naturally routes around it when
choosing assignments, not just when drawing the route afterward.

This class does not touch routing.py or flood.py — pure composition, per
the phase-plan rule of not rewriting earlier phases.
"""

from scipy.optimize import linear_sum_assignment


class DispatchEngine:
    def __init__(self, routing_engine):
        self.engine = routing_engine

    def dispatch(self, vehicles: list, victims: list) -> dict:
        """
        vehicles / victims: list of [lat, lon] pairs.

        Returns a dict with:
          - assignments: list of {vehicle_index, victim_index, travel_time_seconds, route_coords}
          - unreachable: list of {vehicle_index, victim_index} pairs the optimizer
            had to fall back on because no path existed (flood cut them off entirely)
          - total_travel_time_seconds: sum across all assignments (the quantity
            the Hungarian algorithm actually minimizes)
        """
        if not vehicles or not victims:
            return {"assignments": [], "unreachable": [], "total_travel_time_seconds": 0}

        vehicle_nodes = [self.engine.nearest_node(lat, lon) for lat, lon in vehicles]
        victim_nodes = [self.engine.nearest_node(lat, lon) for lat, lon in victims]

        n, m = len(vehicle_nodes), len(victim_nodes)

        # Cache shortest_path results since we need both the cost (for the
        # matrix) and the full route (for the response) — no need to compute twice.
        path_cache = {}
        LARGE_BUT_FINITE = 10_000_000  # stand-in for "practically unreachable" so
        # the optimizer can still produce a valid assignment even if some
        # vehicle/victim pair is fully cut off by flooding, rather than crashing.

        cost_matrix = [[0.0] * m for _ in range(n)]
        for i, vnode in enumerate(vehicle_nodes):
            for j, victim_node in enumerate(victim_nodes):
                path, travel_time, coords = self.engine.shortest_path(vnode, victim_node)
                path_cache[(i, j)] = (path, travel_time, coords)
                cost_matrix[i][j] = travel_time if travel_time != float("inf") else LARGE_BUT_FINITE

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        assignments = []
        unreachable = []
        total_time = 0.0

        for i, j in zip(row_ind, col_ind):
            path, travel_time, coords = path_cache[(int(i), int(j))]
            if travel_time == float("inf"):
                unreachable.append({"vehicle_index": int(i), "victim_index": int(j)})
                continue

            assignments.append({
                "vehicle_index": int(i),
                "victim_index": int(j),
                "travel_time_seconds": travel_time,
                "route_coords": coords,
            })
            total_time += travel_time

        return {
            "assignments": assignments,
            "unreachable": unreachable,
            "total_travel_time_seconds": total_time,
        }
