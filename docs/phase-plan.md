# Phase Plan — Flood-Aware Evacuation Routing

This is the permanent build plan. Each phase is additive — later phases import
and extend earlier modules, nothing gets thrown away and rewritten.

## Requirement → Phase Mapping

| Problem statement requirement | Phase | Status |
|---|---|---|
| Real road network, in-memory (no batch pipeline) | Phase 1 | ✅ Built |
| Shortest-path routing | Phase 1 | ✅ Built |
| No commercial map APIs (OSM only) | Phase 1 | ✅ Built |
| Real-time flood depth updates | Phase 2 | ⏳ Not started |
| Recompute under 1 second (measured + shown) | Phase 2 | ⏳ Not started |
| Continuous path recalculation | Phase 2 | ⏳ Not started |
| Optimize rescue fleet deployment | Phase 3 | ⏳ Not started |
| Safe-zone mapping | Phase 4 | ⏳ Not started |
| Shifting environmental conditions (auto/live) | Phase 5 | ⏳ Not started |
| Demo polish, legend, latency readout | Phase 6 | ⏳ Not started |
| Pitch script, backup video | Phase 7 | ⏳ Not started |

## Phase 1 — Core Routing (done)

**Files:** `backend/config.py`, `backend/engine/routing.py`, `backend/app.py`,
`backend/tests/test_routing.py`, `frontend/*`

**What it does:** Loads a real OSM road network into memory, computes
shortest paths via Dijkstra (NetworkX), exposes it over a REST API, and
renders it on a Leaflet map with click-to-route testing.

**Definition of done:** Backend `/health` returns `"status": "ready"`.
Clicking two points on the frontend map draws a route and logs a
recompute time in milliseconds.

## Phase 2 — Flood Simulation (next)

**Files to add:** `backend/engine/flood.py` (currently a stub), new
endpoints in `app.py` (`/flood/random`, `/flood/reset`), a WebSocket
endpoint (`/ws`) for live push updates.

**What it will do:** A `FloodSimulator` class mutates `RoutingEngine.G` edge
weights live — marking edges flooded (impassable or heavily penalized) and
reversible via a stored original-weights map. Routes recomputed after a
flood event must avoid flooded edges, and recompute time must be logged and
verified under 1 second.

## Phase 3 — Fleet Dispatch

**Files to add:** `backend/engine/dispatch.py` (currently a stub), new
`/dispatch` endpoint.

**What it will do:** Given N vehicle coordinates and M victim coordinates,
build a cost matrix from `RoutingEngine.shortest_path()` calls and run
`scipy.optimize.linear_sum_assignment` (Hungarian algorithm) for the
optimal minimum-total-time assignment.

## Phase 4 — Safe Zones

**What it will do:** Hardcoded safe-zone coordinates (shelters/schools),
shown distinctly on the map. Victims route to the nearest *reachable* safe
zone — if flooding cuts off the nearest one, routing falls back to the next
nearest.

## Phase 5 — Continuous Live Conditions

**What it will do:** A background async task in `app.py` that triggers
small flood events automatically on a timer, broadcasting over the existing
WebSocket without requiring a button click — demonstrates "shifting
environmental conditions" directly from the problem statement's expected
outcome.

## Phase 6 — Frontend Polish

Map legend, on-screen recompute-time readout, cleaner styling.

## Phase 7 — Demo & Pitch

Scripted demo sequence, rehearsed timing, backup video, talking points tied
to each constraint.

---

**Rule for every phase:** don't touch files from a previous phase unless
you're genuinely extending them (e.g. adding a new endpoint to `app.py` is
fine — rewriting `routing.py`'s core logic is not, unless a real bug is
found). This keeps earlier, tested phases stable as you build on top.
