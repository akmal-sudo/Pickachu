# Phase Plan — Flood-Aware Evacuation Routing

This is the permanent build plan. Each phase is additive — later phases import
and extend earlier modules, nothing gets thrown away and rewritten.

## Requirement → Phase Mapping

| Problem statement requirement | Phase | Status |
|---|---|---|
| Real road network, in-memory (no batch pipeline) | Phase 1 | ✅ Built |
| Shortest-path routing | Phase 1 | ✅ Built |
| No commercial map APIs (OSM only) | Phase 1 | ✅ Built |
| Real-time flood depth updates | Phase 2 | ✅ Built |
| Recompute under 1 second (measured + shown) | Phase 2 | ✅ Built |
| Continuous path recalculation | Phase 2 | ✅ Built |
| Optimize rescue fleet deployment | Phase 3 | ✅ Built |
| Safe-zone mapping | Phase 4 | ✅ Built |
| Shifting environmental conditions (auto/live) | Phase 5 | ✅ Built |
| Demo polish, legend, latency readout | Phase 6 | ✅ Built |
| Pitch script, backup video | Phase 7 | ✅ Built |

## Phase 1 — Core Routing (done)

**Files:** `backend/config.py`, `backend/engine/routing.py`, `backend/app.py`,
`backend/tests/test_routing.py`, `frontend/*`

**What it does:** Loads a real OSM road network into memory, computes
shortest paths via Dijkstra (NetworkX), exposes it over a REST API, and
renders it on a Leaflet map with click-to-route testing.

**Definition of done:** Backend `/health` returns `"status": "ready"`.
Clicking two points on the frontend map draws a route and logs a
recompute time in milliseconds.

## Phase 2 — Flood Simulation (done)

**Files:** `backend/engine/flood.py`, `backend/tests/test_flood.py`, new
endpoints in `app.py` (`/flood/random`, `/flood/reset`, `/flood/active`), a
WebSocket endpoint (`/ws`) for live push updates. Frontend additions in
`frontend/js/app.js`, `frontend/index.html`, `frontend/css/style.css`.

**What it does:** A `FloodSimulator` class mutates `RoutingEngine.G` edge
weights live using a depth-based model (mild/heavy penalty below 60cm,
impassable at 60cm+), reversible via a stored original-weights map that
survives repeated re-flooding of the same edge. `/route` now reports which
flooded-but-passable edges a returned path crosses. The frontend keeps a
WebSocket open, draws flood markers live, and auto-recomputes the
currently-displayed route whenever a flood or reset event arrives —
satisfying "continuous path recalculation" without requiring a re-click.
`flood_apply_ms` and `recompute_ms` are reported separately so both halves
of the <1s constraint are provable on their own.

**Definition of done:** `pytest` passes (11/11, including 8 new flood
tests). Clicking "Simulate Flood" shows markers appear live on all open
tabs, and any currently-drawn route redraws itself if it's affected —
without the user clicking anything else.

## Phase 3 — Fleet Dispatch (done)

**Files:** `backend/engine/dispatch.py`, `backend/tests/test_dispatch.py`,
`/dispatch` endpoint in `app.py`, vehicle/victim placement + dispatch
rendering in the frontend.

**What it does:** Given N vehicle coordinates and M victim coordinates,
builds a cost matrix from `RoutingEngine.shortest_path()` calls and runs
`scipy.optimize.linear_sum_assignment` (Hungarian algorithm) for the
optimal minimum-total-fleet-time assignment — not just nearest-vehicle
greedy matching. Automatically flood-aware since it reuses the same
`shortest_path()` the rest of the app uses.

**Definition of done:** Placing vehicles/victims and clicking "Run
Dispatch" draws one route per assignment, broadcasts to all connected
clients, and reports `dispatch_ms`.

## Phase 4 — Safe Zones (done)

**Files:** `backend/engine/safezone.py`, `backend/tests/test_safezone.py`,
`SAFE_ZONES` list in `config.py`, `/safezone/list` + `/safezone/route`
endpoints, safe-zone markers + "Route Victims Home" in the frontend.

**What it does:** `SafeZoneRouter` holds a fixed list of shelter/school
coordinates and, for any victim location, tries every safe zone ordered by
travel time, returning the first one that's actually reachable — not just
geographically nearest. If flooding has fully cut off the closest zone,
it transparently falls back to the next, and reports which zones were
skipped and why.

**Definition of done:** Clicking "Route Victims Home" draws each victim's
route to their nearest *reachable* shelter; flooding the road to the
nearest shelter and re-running visibly reroutes to the next-nearest one.

## Phase 5 — Continuous Live Conditions (done)

**Files:** `backend/engine/live.py`, `backend/tests/test_live.py`,
`recede_random()` added to `flood.py`, `/live/start` + `/live/stop` +
`/live/status` endpoints, Start/Stop Live Mode buttons + live pulse
indicator in the frontend.

**What it does:** `LiveConditions` runs a background asyncio loop, ticking
every `LIVE_FLOOD_INTERVAL_SECONDS` (default **0.2s**), that on each tick
either floods 1–2 new random edges or lets 1–2 already-flooded edges
recede — a continuously shifting flood state, broadcast over the existing
WebSocket, with zero button clicks required once started. Framework-
agnostic (asyncio + a broadcast callback only) so it's unit-testable
without spinning up FastAPI. Frontend recompute calls are debounced
(400ms) so a 0.2s tick rate doesn't hammer `/route`.

**Definition of done:** Clicking "Start Live Mode" causes flood markers to
appear and disappear on their own, the live pulse indicator turns green,
and any on-screen route keeps recomputing without further clicks; "Stop
Live Mode" halts it cleanly with no further events.

## Phase 6 — Frontend Polish (done)

**Files:** `frontend/index.html`, `frontend/css/style.css`,
`frontend/js/app.js`.

**What it does:** An always-visible stats bar shows the last route
recompute time, flood-apply time, and dispatch time — each color-coded
green/red against the 1-second constraint — plus a live-mode indicator. A
map legend explains every marker/line color. Buttons are grouped into
labeled sections (Flooding / Fleet Dispatch / Safe Zones) instead of one
undifferentiated block.

## Phase 7 — Demo & Pitch (done)

**Files:** `docs/pitch-script.md`, `docs/backup-plan.md`.

**What it does:** A timed (~4–5 min) demo sequence with talking points
tied explicitly to each constraint from the problem statement, anticipated
Q&A (including an honest answer on where flood data actually comes from
today), and a backup plan — pre-recorded video, cache pre-warming, and a
fallback ladder for if live demo conditions fail.

---

**Rule for every phase:** don't touch files from a previous phase unless
you're genuinely extending them (e.g. adding a new endpoint to `app.py` is
fine — rewriting `routing.py`'s core logic is not, unless a real bug is
found). This keeps earlier, tested phases stable as you build on top.
