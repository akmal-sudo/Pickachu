# Pitch Script — Flood-Aware Evacuation Routing

Total target: 4–5 minutes live demo + 1–2 minutes Q&A buffer. Rehearse this
with a timer before presenting — cut talking, never cut the demo steps.

---

## 0. Open (20s)

> "Standard navigation apps route emergency responders straight into
> submerged roads during flash floods, because they don't know the water is
> there. We built a routing engine that does — it recomputes in real time as
> conditions change, with zero batch processing and zero commercial map
> APIs."

Have the app already open, backend already running, `/health` already
confirmed `ready` — **never let graph loading happen on stage.**

## 1. Core routing — prove the constraints (45s)

- Click two points on the map. Route draws.
- Point at the stats bar: **"recompute: X ms"**.
- Say: *"That's the full round trip — snap-to-road, Dijkstra over the real
  OpenStreetMap network, back to the browser. No Google Maps, no
  precomputed tiles, no database — this graph lives in memory and every
  route is computed fresh."*

This single click covers **two of your three hard constraints**
(zero-pipeline, no commercial map APIs) in one visual.

## 2. Flood reactivity — the headline feature (60s)

- With the route still on screen, click **Simulate Flood**.
- Flood markers appear. If one crosses the current route, **it redraws
  itself automatically** — point at this happening without you clicking
  anything.
- Point at the stats bar again: **flood apply: X ms**, **recompute: X ms**
  — both comfortably under 1000ms.
- Say: *"This is 'recompute under one second when new environmental data
  arrives' — proven live, not simulated after the fact. Depth matters too:
  shallow water gets a penalty, not a full block — the router still
  prefers a fast road with a puddle over a long detour, exactly like a
  human driver would reason."*

## 3. Live mode — continuous conditions (30s)

- Click **Start Live Mode**.
- Point at the green pulsing "Live mode: on" indicator and the flood
  markers appearing/disappearing on their own at a 0.2s tick.
- Say: *"This is the 'shifting environmental conditions' requirement — no
  button clicks, the map is reacting to a live feed the same way it would
  react to real sensor data arriving over a WebSocket."*
- Click **Stop Live Mode** before moving on — don't let it run distractingly
  through the rest of the demo.

## 4. Fleet dispatch — the optimization story (45s)

- Click **Route Mode → Place Vehicle** (2–3 clicks), then **Place Victim**
  (2–3 clicks).
- Click **Run Dispatch**.
- Point at the colored routes and the stats bar's **dispatch: X ms**.
- Say: *"This isn't 'send the nearest ambulance to each call' — that's
  provably suboptimal once you have multiple vehicles and multiple victims.
  This is the Hungarian algorithm solving the assignment that minimizes
  TOTAL fleet response time, and it's flood-aware for free, because it's
  built on the exact same shortest-path calls the map uses — a flooded
  road makes an assignment more expensive, so the optimizer routes around
  it automatically."*

## 5. Safe zones (30s)

- Click **Show Safe Zones** — school/shelter icons appear.
- Click **Route Victims Home**.
- Say: *"Every victim routes to their nearest reachable shelter — if
  flooding cuts off the closest one, it falls back to the next nearest
  automatically."* If you have time, flood the edge leading to the nearest
  shelter first, then show the fallback happening live — this is a strong
  visual if you can fit it.

## 6. Close (20s)

> "Every number you saw was live, not a slide — sub-second recompute, zero
> pipeline, real open-map data. The one gap, and we want to be upfront
> about it: road-level flood depth isn't published as open real-time data
> anywhere in India yet — CWC and IMD monitor river gauges, not street
> segments. What we've built is the reactive engine ready to consume that
> feed the moment it exists, or from municipal sensors, or crowdsourced
> reports — the hard, provable part is done."

---

## If something breaks live

- **Backend didn't load / crashed:** switch immediately to the backup
  video (see `backup-plan.md`). Don't debug on stage.
- **A flood makes the demo route fully unreachable:** click **Reset
  Floods**, re-click your two points, continue. This is a 2-second recovery
  — don't apologize for it, it's the system working correctly (blocking an
  impassable road is the point).
- **WebSocket disconnects:** the frontend auto-reconnects every 2s — just
  keep talking for a beat, it'll recover on its own.

## Anticipated questions (see also: `docs/data-sources-explainer.md` if you
have one from earlier planning)

- **"Where does the flood data actually come from?"** → be honest: it's
  simulated because road-segment-level real-time flood depth isn't public
  open data in India today (CWC/IMD monitor river gauges, not streets).
  The system is built so a real feed — CWC bulletins, municipal sensors,
  crowdsourced reports — could be plugged in through the exact same
  `FloodSimulator` interface without touching the routing or dispatch code.
- **"Does this work in other cities?"** → yes, `config.py`'s `PLACE_NAME`
  is the only thing that changes; the routing/flood/dispatch engine is
  location-agnostic. OSM coverage density varies by city tier (Tier 1
  metros are mapped densely, some Tier 3 towns less so) — worth naming
  proactively rather than waiting to be asked.
- **"Why Hungarian algorithm and not just nearest-vehicle?"** → nearest-
  vehicle-per-victim is a greedy heuristic that can be badly suboptimal
  once you have more than one of each — Hungarian solves the true
  minimum-total-time assignment exactly, and it's still fast (polynomial
  time) at fleet sizes this demo would ever show.
