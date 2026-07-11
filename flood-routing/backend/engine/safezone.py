"""
Phase 4 — Safe zones.

SafeZoneRouter takes a fixed list of safe-zone coordinates (shelters,
schools) and, for any given victim location, finds the NEAREST REACHABLE
one — not just the geographically nearest. If flooding has cut off the
closest safe zone entirely (shortest_path returns inf), this falls back to
the next nearest, and the next, until it finds one still reachable.

Composes on top of RoutingEngine.shortest_path() exactly like dispatch.py
does — same reasoning: it automatically respects whatever flood state is
currently active, without safezone.py needing to know anything about
flood.py.
"""


class SafeZoneRouter:
    def __init__(self, routing_engine, safe_zones: list):
        """
        safe_zones: list of {"name": str, "lat": float, "lon": float}
        """
        self.engine = routing_engine
        self.safe_zones = safe_zones
        # Cache safe-zone -> nearest graph node once; safe zones don't move.
        self._zone_nodes = [
            (zone, self.engine.nearest_node(zone["lat"], zone["lon"]))
            for zone in safe_zones
        ]

    def list_zones(self) -> list:
        return [{"name": z["name"], "lat": z["lat"], "lon": z["lon"]} for z in self.safe_zones]

    def route_to_nearest(self, victim_lat: float, victim_lon: float) -> dict:
        """
        Tries every safe zone, closest-by-travel-time first, and returns the
        first one that's actually reachable. Also reports which zones (if
        any) were skipped because flooding cut them off — good demo detail:
        "nearest zone was cut off by flooding, rerouted to next nearest."
        """
        victim_node = self.engine.nearest_node(victim_lat, victim_lon)

        candidates = []
        for zone, zone_node in self._zone_nodes:
            path, travel_time, coords = self.engine.shortest_path(victim_node, zone_node)
            candidates.append({
                "zone": zone,
                "travel_time_seconds": travel_time,
                "route_coords": coords,
                "reachable": travel_time != float("inf"),
            })

        candidates.sort(key=lambda c: c["travel_time_seconds"])

        reachable = [c for c in candidates if c["reachable"]]
        skipped = [c for c in candidates if not c["reachable"]]

        if not reachable:
            return {
                "chosen_zone": None,
                "route_coords": [],
                "travel_time_seconds": None,  # inf isn't valid JSON — None means "no reachable zone"
                "skipped_zones": [c["zone"]["name"] for c in skipped],
                "all_zones_unreachable": True,
            }

        best = reachable[0]
        # Any reachable zone that ranked worse than 'best' AND any fully
        # unreachable zone both count as "skipped" for the demo narrative —
        # but only report unreachable ones as flood-caused skips explicitly.
        return {
            "chosen_zone": best["zone"],
            "route_coords": best["route_coords"],
            "travel_time_seconds": best["travel_time_seconds"],
            "skipped_zones": [c["zone"]["name"] for c in skipped],
            "all_zones_unreachable": False,
        }
