"""
Phase 2 — Flood simulation.

FloodSimulator mutates a RoutingEngine's graph (G) live: it raises travel_time
on chosen edges to simulate flood depth, and can fully reverse those changes.
Nothing here touches routing.py — this class is layered on top of a
RoutingEngine instance, per the phase-plan rule of not rewriting earlier phases.

Depth model:
    < 30cm   -> mild penalty   (still passable, but discouraged)
    30-60cm  -> heavy penalty  (avoided unless there's no alternative)
    >= 60cm  -> impassable     (travel_time = inf, routing will never use it)
"""

import random


class FloodSimulator:
    def __init__(self, engine):
        self.engine = engine
        # (u, v, k) -> original travel_time, saved the FIRST time an edge is
        # touched. Never overwritten again, so repeated floods on the same
        # edge and later reset() always recover the true original value.
        self._original_weights = {}
        # (u, v, k) -> current flood depth in cm, only for currently-flooded edges.
        self._flooded = {}

    @staticmethod
    def _penalty_for_depth(depth_cm: float) -> float:
        """Returns a multiplier to apply to the original travel_time, or inf."""
        if depth_cm >= 60:
            return float("inf")
        elif depth_cm >= 30:
            return 20.0
        else:
            return 3.0

    def flood_edge(self, u, v, k: int, depth_cm: float) -> dict:
        """Floods a single edge to the given depth. Returns the event dict."""
        G = self.engine.G
        key = (u, v, k)

        if key not in self._original_weights:
            self._original_weights[key] = G.edges[u, v, k]["travel_time"]

        base = self._original_weights[key]
        penalty = self._penalty_for_depth(depth_cm)
        new_weight = float("inf") if penalty == float("inf") else base * penalty

        G.edges[u, v, k]["travel_time"] = new_weight
        G.edges[u, v, k]["flood_depth_cm"] = depth_cm
        self._flooded[key] = depth_cm

        return {
            "u": u, "v": v, "k": k,
            "depth_cm": depth_cm,
            "impassable": penalty == float("inf"),
            "coords": [
                [G.nodes[u]["y"], G.nodes[u]["x"]],
                [G.nodes[v]["y"], G.nodes[v]["x"]],
            ],
        }

    def flood_random(self, n: int = 5, min_depth: int = 10, max_depth: int = 80) -> list:
        """Floods n random edges with random depths in [min_depth, max_depth]. Returns the events."""
        edges = list(self.engine.G.edges(keys=True))
        n = min(n, len(edges))
        chosen = random.sample(edges, n)
        return [
            self.flood_edge(u, v, k, random.randint(min_depth, max_depth))
            for (u, v, k) in chosen
        ]

    def reset(self) -> int:
        """Restores every flooded edge to its original travel_time. Returns count reset."""
        G = self.engine.G
        count = 0
        for (u, v, k), original in self._original_weights.items():
            G.edges[u, v, k]["travel_time"] = original
            G.edges[u, v, k].pop("flood_depth_cm", None)
            count += 1
        self._original_weights.clear()
        self._flooded.clear()
        return count

    def recede_random(self, n: int = 1) -> list:
        """
        Phase 5 — un-floods n currently-flooded edges (water receding),
        restoring each to its true original travel_time. Returns the
        restored edge keys. This is what makes live mode feel like
        "shifting conditions" rather than the map monotonically filling up
        with flood markers forever.
        """
        keys = list(self._flooded.keys())
        n = min(n, len(keys))
        if n == 0:
            return []
        chosen = random.sample(keys, n)

        G = self.engine.G
        events = []
        for (u, v, k) in chosen:
            original = self._original_weights.pop((u, v, k))
            G.edges[u, v, k]["travel_time"] = original
            G.edges[u, v, k].pop("flood_depth_cm", None)
            del self._flooded[(u, v, k)]
            events.append({"u": u, "v": v, "k": k})
        return events

    def active_floods(self) -> list:
        """Returns current flood events, e.g. for a frontend reconnecting mid-demo."""
        G = self.engine.G
        events = []
        for (u, v, k), depth in self._flooded.items():
            events.append({
                "u": u, "v": v, "k": k,
                "depth_cm": depth,
                "impassable": depth >= 60,
                "coords": [
                    [G.nodes[u]["y"], G.nodes[u]["x"]],
                    [G.nodes[v]["y"], G.nodes[v]["x"]],
                ],
            })
        return events

    def path_crosses_flood(self, path: list) -> list:
        """
        Given a node path (list of node ids from shortest_path), returns the
        subset of currently-flooded edges that the path crosses — even ones
        that are passable-but-penalized. Useful for warning a responder that
        their route crosses a mild flood, not just for blocking impassable ones.
        """
        crossed = []
        path_edges = set(zip(path, path[1:])) if path else set()
        for (u, v, k), depth in self._flooded.items():
            if (u, v) in path_edges:
                crossed.append({"u": u, "v": v, "k": k, "depth_cm": depth})
        return crossed
