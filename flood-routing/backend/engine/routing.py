"""
Phase 1 — Core routing engine.

Loads a real road network into memory (no database, no batch pipeline —
satisfies the "zero-pipeline processing" constraint) and computes shortest
paths on it.

Phase 2 (flood.py) will mutate this graph's edge weights live.
Phase 3 (dispatch.py) will call shortest_path() repeatedly to build a cost
matrix for multi-vehicle assignment.

Keeping this class dependency-free of flood/dispatch logic is intentional —
each phase should be able to import and extend this without editing it.
"""

import networkx as nx
import osmnx as ox


class RoutingEngine:
    def __init__(self, place_name: str, network_type: str = "drive", dist_meters: int = 2000):
        """
        place_name: an address or place OSMnx/Nominatim can geocode to a POINT
                    (e.g. 'Fort Kochi, Kerala, India'). This does NOT need a
                    polygon boundary — a plain point match is enough.
        dist_meters: radius around that point to pull the road network for.
                     2000m is a good hackathon-demo size (small, fast to load).
        """
        self.place_name = place_name
        self.network_type = network_type
        self.dist_meters = dist_meters
        self.G: nx.MultiDiGraph | None = None

    def load(self) -> "RoutingEngine":
        """
        Downloads the road graph and precomputes travel times. Call once at startup.

        Uses graph_from_address (point + radius) instead of graph_from_place
        (which requires Nominatim to return a polygon boundary — this fails
        for a lot of neighborhood-level names, e.g. 'Fort Kochi').
        """
        self.G = ox.graph_from_address(
            self.place_name,
            dist=self.dist_meters,
            network_type=self.network_type,
        )
        self.G = ox.add_edge_speeds(self.G)
        self.G = ox.add_edge_travel_times(self.G)
        return self

    def stats(self) -> dict:
        return {"nodes": len(self.G.nodes), "edges": len(self.G.edges)}

    def bounds_center(self) -> list:
        """Returns [lat, lon] center of the loaded graph — used to initialize the frontend map."""
        ys = [data["y"] for _, data in self.G.nodes(data=True)]
        xs = [data["x"] for _, data in self.G.nodes(data=True)]
        return [sum(ys) / len(ys), sum(xs) / len(xs)]

    def nearest_node(self, lat: float, lon: float):
        """Snaps a raw lat/lon (e.g. a map click) to the nearest graph node."""
        return ox.nearest_nodes(self.G, lon, lat)

    def nearest_edge(self, lat: float, lon: float):
        """
        Snaps a raw lat/lon (e.g. a map click) to the nearest graph EDGE,
        returning (u, v, k) — used by the "choose your own flood spot"
        feature so a user can flood a specific road instead of only random
        ones. Doesn't touch nearest_node's behavior or any existing caller.
        """
        u, v, k = ox.nearest_edges(self.G, lon, lat)
        return u, v, k

    def shortest_path(self, orig_node, dest_node):
        """
        Returns (node_path, total_travel_time_seconds, route_coords).
        route_coords is a list of [lat, lon] pairs ready for the frontend to draw.
        """
        try:
            path = nx.shortest_path(self.G, orig_node, dest_node, weight="travel_time")
        except nx.NetworkXNoPath:
            return None, float("inf"), []

        travel_time = nx.shortest_path_length(self.G, orig_node, dest_node, weight="travel_time")
        coords = [[self.G.nodes[n]["y"], self.G.nodes[n]["x"]] for n in path]
        return path, travel_time, coords