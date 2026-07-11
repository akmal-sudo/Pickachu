"""
FastAPI entrypoint.

Run from inside backend/:
    uvicorn app:app --reload --port 8000

Phase 1 endpoints only: health check, graph bounds, single-route computation.
Phase 2 will add /flood/* endpoints + a WebSocket for live updates.
Phase 3 will add /dispatch.
"""

import time
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import PLACE_NAME, NETWORK_TYPE
from engine import RoutingEngine

app = FastAPI(title="Flood-Aware Evacuation Routing — Phase 1: Core Routing")

# Wide open CORS for hackathon speed — frontend runs from a local file/different port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: RoutingEngine | None = None


@app.on_event("startup")
def startup():
    global engine
    print(f"[startup] Loading road network for '{PLACE_NAME}' ...")
    engine = RoutingEngine(PLACE_NAME, NETWORK_TYPE).load()
    print(f"[startup] Graph ready: {engine.stats()}")


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

    return {
        "travel_time_seconds": travel_time,
        "route_coords": coords,
        "recompute_ms": round(elapsed_ms, 2),
    }
