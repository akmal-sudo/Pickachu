"""
Tests for Phase 5 — recede_random() on FloodSimulator, and the LiveConditions
background loop. The loop itself uses asyncio.sleep/create_task, so these
tests run it briefly with asyncio.run() and a short interval rather than
mocking asyncio internals.
"""

import asyncio

import networkx as nx
from engine.routing import RoutingEngine
from engine.flood import FloodSimulator
from engine.live import LiveConditions


def _build_test_engine():
    G = nx.MultiDiGraph()
    G.add_node(1, x=0.000, y=0.000)
    G.add_node(2, x=0.001, y=0.000)
    G.add_node(3, x=0.002, y=0.000)
    G.add_edge(1, 2, key=0, travel_time=10)
    G.add_edge(2, 3, key=0, travel_time=10)
    G.add_edge(1, 3, key=0, travel_time=50)

    engine = RoutingEngine("test-area")
    engine.G = G
    return engine


def test_recede_random_restores_only_flooded_edges():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(1, 2, 0, depth_cm=70)

    events = sim.recede_random(n=1)

    assert len(events) == 1
    assert engine.G.edges[1, 2, 0]["travel_time"] == 10
    assert sim.active_floods() == []


def test_recede_random_on_empty_state_is_a_safe_noop():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    events = sim.recede_random(n=3)
    assert events == []


def test_recede_random_caps_to_available_flooded_edges():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    sim.flood_edge(1, 2, 0, depth_cm=40)
    events = sim.recede_random(n=99)
    assert len(events) == 1  # only one edge was actually flooded


def test_live_conditions_start_stop_toggles_running_flag():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)
    broadcasts = []

    async def fake_broadcast(msg):
        broadcasts.append(msg)

    async def run():
        live = LiveConditions(sim, fake_broadcast, interval=0.01)
        assert live.running is False
        live.start()
        assert live.running is True
        await asyncio.sleep(0.05)  # let a few ticks happen
        live.stop()
        assert live.running is False
        return live

    asyncio.run(run())
    # At 0.01s interval over ~0.05s we expect at least one tick to have
    # fired and broadcast something (flood or recede).
    assert len(broadcasts) >= 1
    assert broadcasts[0]["type"] in ("flood", "recede")


def test_live_conditions_double_start_does_not_spawn_second_loop():
    engine = _build_test_engine()
    sim = FloodSimulator(engine)

    async def fake_broadcast(msg):
        pass

    async def run():
        live = LiveConditions(sim, fake_broadcast, interval=0.01)
        live.start()
        first_task = live._task
        live.start()  # should be a no-op since already running
        second_task = live._task
        live.stop()
        return first_task, second_task

    first_task, second_task = asyncio.run(run())
    assert first_task is second_task
