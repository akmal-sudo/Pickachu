"""
FastAPI entrypoint.

Run from inside backend/:
    uvicorn app:app --reload --port 8000

Phase 1 endpoints: health check, graph bounds, single-route computation.
Phase 2 adds: /flood/* endpoints + a WebSocket (/ws) for live push updates.
Phase 3 adds: /dispatch — optimal multi-vehicle-to-multi-victim assignment.
Phase 4 adds: /safezone/* — route victims to the nearest reachable safe zone.
Phase 5 adds: /live/* — background auto-flood/recede loop (0.2s default tick).
"""

import time
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import PLACE_NAME, NETWORK_TYPE, SAFE_ZONES, LIVE_FLOOD_INTERVAL_SECONDS
from engine import RoutingEngine, FloodSimulator, DispatchEngine, SafeZoneRouter, LiveConditions

app = FastAPI(title="Flood-Aware Evacuation Routing — Phase 5: Continuous Live Conditions")

# Wide open CORS for hackathon speed — frontend runs from a local file/different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: RoutingEngine | None = None
flood_sim: FloodSimulator | None = None
dispatch_engine: DispatchEngine | None = None
safezone_router: SafeZoneRouter | None = None
live_conditions: LiveConditions | None = None


class ConnectionManager:
    """Tracks live WebSocket clients and broadcasts flood/reset events to all of them."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.on_event("startup")
def startup():
    global engine, flood_sim, dispatch_engine, safezone_router, live_conditions
    print(f"[startup] Loading road network for '{PLACE_NAME}' ...")
    engine = RoutingEngine(PLACE_NAME, NETWORK_TYPE).load()
    flood_sim = FloodSimulator(engine)
    dispatch_engine = DispatchEngine(engine)
    safezone_router = SafeZoneRouter(engine, SAFE_ZONES)
    live_conditions = LiveConditions(flood_sim, manager.broadcast, interval=LIVE_FLOOD_INTERVAL_SECONDS)
    print(f"[startup] Graph ready: {engine.stats()}")


@app.on_event("shutdown")
async def shutdown():
    if live_conditions is not None:
        live_conditions.stop()


@app.get("/health")
def health():
    """Use this to confirm the graph finished loading before hitting other endpoints."""
    if engine is None or engine.G is None:
        return {"status": "loading"}
    return {"status": "ready", **engine.stats()}


@app.get("/graph/bounds")
def graph_bounds():
    """Center point the frontend uses to initialize the map view."""
    return {"center": engine.bounds_center()}


class RouteRequest(BaseModel):
    origin: List[float]       # [lat, lon]
    destination: List[float]  # [lat, lon]


@app.post("/route")
def get_route(req: RouteRequest):
    """Computes shortest path and reports recompute time — this is your proof of the <1s constraint."""
    start = time.time()
    orig_node = engine.nearest_node(*req.origin)
    dest_node = engine.nearest_node(*req.destination)
    path, travel_time, coords = engine.shortest_path(orig_node, dest_node)
    elapsed_ms = (time.time() - start) * 1000

    # Phase 2: flag any currently-flooded (but passable) edges this route
    # crosses, so a responder sees "this route works but crosses a 15cm
    # puddle on X Road" rather than a silent number.
    crossed = flood_sim.path_crosses_flood(path) if path else []

    return {
        "travel_time_seconds": travel_time,
        "route_coords": coords,
        "recompute_ms": round(elapsed_ms, 2),
        "crosses_flooded_edges": crossed,
    }


# ---------------------------------------------------------------------------
# Phase 2 — Flood simulation endpoints + live WebSocket push
# ---------------------------------------------------------------------------

class FloodRandomRequest(BaseModel):
    n: int = 5
    min_depth: int = 10
    max_depth: int = 80


@app.post("/flood/random")
async def flood_random(req: FloodRandomRequest):
    """
    Floods n random edges and broadcasts the event to all connected clients.
    Reports flood_apply_ms separately from route recompute_ms — mutating the
    graph and recomputing a route are two different operations, and the
    <1s constraint applies to both.
    """
    start = time.time()
    events = flood_sim.flood_random(n=req.n, min_depth=req.min_depth, max_depth=req.max_depth)
    elapsed_ms = round((time.time() - start) * 1000, 2)

    message = {"type": "flood", "events": events, "flood_apply_ms": elapsed_ms}
    await manager.broadcast(message)

    return message


class FloodAtRequest(BaseModel):
    lat: float
    lon: float
    depth_cm: float = 70  # defaults to impassable, since a deliberately-chosen flood is usually meant to be seen blocking something


@app.post("/flood/at")
async def flood_at(req: FloodAtRequest):
    """
    Floods the specific road nearest to a clicked point — for demoing a
    chosen scenario (e.g. "flood the bridge on the current route") rather
    than only random flooding. Uses the exact same FloodSimulator.flood_edge()
    that flood_random() calls, so it's reversible/reset the same way and
    behaves identically once applied — the only difference is which edge
    gets picked.
    """
    start = time.time()
    u, v, k = engine.nearest_edge(req.lat, req.lon)
    event = flood_sim.flood_edge(u, v, k, req.depth_cm)
    elapsed_ms = round((time.time() - start) * 1000, 2)

    message = {"type": "flood", "events": [event], "flood_apply_ms": elapsed_ms}
    await manager.broadcast(message)

    return message


@app.post("/flood/reset")
async def flood_reset():
    """Restores every flooded edge and broadcasts a reset event."""
    count = flood_sim.reset()
    message = {"type": "reset", "count": count}
    await manager.broadcast(message)
    return message


@app.get("/flood/active")
def flood_active():
    """Current flood state — used by a frontend that just (re)connected mid-demo."""
    return {"events": flood_sim.active_floods()}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Live push channel. On connect, immediately sends current flood state so a
    late-joining client is in sync, then just stays open for broadcasts.
    """
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "flood", "events": flood_sim.active_floods(), "flood_apply_ms": 0})
        while True:
            # We don't expect messages from the client, but need to await
            # something to detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Phase 3 — Fleet dispatch
# ---------------------------------------------------------------------------

class DispatchRequest(BaseModel):
    vehicles: List[List[float]]  # [[lat, lon], ...]
    victims: List[List[float]]   # [[lat, lon], ...]


@app.post("/dispatch")
async def dispatch(req: DispatchRequest):
    """
    Optimal multi-vehicle-to-multi-victim assignment (Hungarian algorithm),
    minimizing TOTAL fleet response time. Automatically flood-aware, since
    it calls the same shortest_path() that flood.py's edge weights affect.
    Broadcasts the result so every connected map shows the same dispatch.
    """
    start = time.time()
    result = dispatch_engine.dispatch(req.vehicles, req.victims)
    elapsed_ms = round((time.time() - start) * 1000, 2)

    message = {"type": "dispatch", **result, "dispatch_ms": elapsed_ms}
    await manager.broadcast(message)
    return message


# ---------------------------------------------------------------------------
# Phase 4 — Safe zones
# ---------------------------------------------------------------------------

@app.get("/safezone/list")
def safezone_list():
    """All configured safe zones — frontend draws these as distinct, fixed markers."""
    return {"zones": safezone_router.list_zones()}


class SafeZoneRouteRequest(BaseModel):
    victim: List[float]  # [lat, lon]


@app.post("/safezone/route")
def safezone_route(req: SafeZoneRouteRequest):
    """
    Routes a single victim to the nearest REACHABLE safe zone. If the
    nearest one is cut off by flooding, this transparently falls back to
    the next nearest — skipped_zones tells you which ones were tried and
    rejected, which is worth surfacing in the demo narrative.
    """
    start = time.time()
    result = safezone_router.route_to_nearest(*req.victim)
    elapsed_ms = round((time.time() - start) * 1000, 2)
    return {**result, "recompute_ms": elapsed_ms}


# ---------------------------------------------------------------------------
# Phase 5 — Continuous live conditions
# ---------------------------------------------------------------------------

@app.post("/live/start")
async def live_start():
    """
    Starts the background flood/recede loop (ticks every
    LIVE_FLOOD_INTERVAL_SECONDS, default 0.2s). Runs until /live/stop is
    called — this is what demonstrates "shifting environmental conditions"
    without any further button clicks.

    Must be async: asyncio.create_task() requires a running event loop, and
    FastAPI runs sync `def` endpoints in a worker thread, not the loop.
    """
    live_conditions.start()
    return {"running": live_conditions.running, "interval_seconds": live_conditions.interval}


@app.post("/live/stop")
async def live_stop():
    live_conditions.stop()
    return {"running": live_conditions.running}


@app.get("/live/status")
def live_status():
    return {"running": live_conditions.running, "interval_seconds": live_conditions.interval}
