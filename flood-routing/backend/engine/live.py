"""
Phase 5 — Continuous live conditions.

LiveConditions runs a background asyncio loop that, once started, ticks
every `interval` seconds (default 0.2s, per the demo requirement) and
either floods a couple of new random edges or lets a couple of already-
flooded edges recede — a small, continuously shifting flood state,
matching the problem statement's "shifting environmental conditions"
expected outcome, with no button click required once it's running.

Deliberately framework-agnostic: it only depends on asyncio + a
FloodSimulator + an async broadcast callback (e.g. ConnectionManager.
broadcast from app.py), not on FastAPI itself, so it's testable in
isolation and follows the same "don't reach into other layers" pattern as
dispatch.py and safezone.py.
"""

import asyncio
import random


class LiveConditions:
    def __init__(self, flood_sim, broadcast_callback, interval: float = 0.2):
        self.flood_sim = flood_sim
        self.broadcast = broadcast_callback
        self.interval = interval
        self._task = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self):
        self.running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        try:
            while self.running:
                await asyncio.sleep(self.interval)
                await self._tick()
        except asyncio.CancelledError:
            pass

    async def _tick(self):
        # Bias toward flooding a bit more than receding, so the map doesn't
        # sit static, but still self-limits since flood_random only ever
        # touches a couple of edges per tick.
        action = random.choices(["flood", "recede"], weights=[0.65, 0.35])[0]

        if action == "flood":
            events = self.flood_sim.flood_random(n=random.randint(1, 2), min_depth=10, max_depth=80)
            if events:
                await self.broadcast({"type": "flood", "events": events, "flood_apply_ms": 0, "live": True})
        else:
            events = self.flood_sim.recede_random(n=random.randint(1, 2))
            if events:
                await self.broadcast({"type": "recede", "events": events, "live": True})
