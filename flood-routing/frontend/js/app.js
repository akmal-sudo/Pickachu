/*
 * Phase 1: initializes the map from the backend's graph bounds, lets the
 * user click two points, and draws the shortest path between them.
 *
 * Phase 2 adds: a WebSocket connection for live flood push updates, flood
 * markers on the map, Simulate/Reset buttons, and auto-recompute of the
 * currently-drawn route if a new flood event touches it.
 *
 * Phase 3 adds: click-to-place vehicle/victim markers, a dispatch button
 * that requests the optimal fleet assignment, and rendering of the
 * resulting per-vehicle routes.
 *
 * Phase 4 adds: safe-zone markers and "route victims to nearest reachable
 * safe zone" (falls back automatically if the nearest one is flooded out).
 *
 * Phase 5 adds: Start/Stop Live Mode, which drives the backend's background
 * flood/recede loop (0.2s default tick) — flood markers now appear AND
 * disappear on their own, and any on-screen route keeps recomputing live,
 * with recompute calls debounced so a 0.2s tick rate doesn't hammer the API.
 *
 * Phase 6 adds: an always-visible stats bar (recompute/flood-apply/dispatch
 * timings + live-mode indicator) and a map legend.
 */

const API = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws";

let map;
let routeLayer;
let floodLayer;
let dispatchLayer;
let safezoneLayer;
let safezoneRouteLayer;
let clickPoints = [];
let clickMarkers = [];
let currentRoute = { origin: null, destination: null }; // last computed route, for auto-recompute
let ws;

// Phase 3 state
let clickMode = "route"; // "route" | "vehicle" | "victim"
let vehicles = []; // [[lat, lon], ...]
let victims = [];  // [[lat, lon], ...]
let vehicleMarkers = [];
let victimMarkers = [];

// Phase 4 state
let safeZones = [];
let safeZonesVisible = false;

// Phase 5 state — track individual flood markers by edge key so "recede"
// events can remove exactly one, instead of wiping the whole layer.
let floodMarkersByKey = {}; // "u-v-k" -> { circle, line }
let lastRecomputeAt = 0;
let recomputeTrailingTimer = null;
const RECOMPUTE_THROTTLE_MS = 400; // guarantees a recompute at least this often, even under continuous flood ticks

const DISPATCH_COLORS = ["#2b8cbe", "#31a354", "#e6550d", "#756bb1", "#636363", "#c51b8a"];

function log(msg) {
  const el = document.getElementById("log");
  el.innerHTML = `${msg}<br>` + el.innerHTML;
}

function setWsStatus(connected) {
  const el = document.getElementById("ws-status");
  el.className = connected ? "connected" : "disconnected";
}

// ---------------------------------------------------------------------------
// Phase 6 — stats bar
// ---------------------------------------------------------------------------

function setStat(id, ms) {
  const el = document.getElementById(id);
  el.textContent = `${ms.toFixed(1)} ms`;
  el.className = "stat-value " + (ms < 1000 ? "ok" : "warn");
}

function setLiveStat(running) {
  document.getElementById("stat-live").textContent = running ? "on" : "off";
  document.getElementById("live-pulse").className = "live-pulse" + (running ? " active" : "");
}

async function init() {
  log("Contacting backend...");
  let bounds;
  try {
    bounds = await fetch(`${API}/graph/bounds`).then((r) => r.json());
  } catch (err) {
    log("❌ Could not reach backend. Is uvicorn running on port 8000?");
    return;
  }

  map = L.map("map").setView(bounds.center, 15);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  routeLayer = L.layerGroup().addTo(map);
  floodLayer = L.layerGroup().addTo(map);
  dispatchLayer = L.layerGroup().addTo(map);
  safezoneLayer = L.layerGroup().addTo(map);
  safezoneRouteLayer = L.layerGroup().addTo(map);

  map.on("click", onMapClick);

  document.getElementById("flood-btn").addEventListener("click", triggerRandomFlood);
  document.getElementById("reset-btn").addEventListener("click", triggerReset);
  document.getElementById("route-mode-btn").addEventListener("click", () => setClickMode("route"));
  document.getElementById("add-vehicle-btn").addEventListener("click", () => setClickMode("vehicle"));
  document.getElementById("add-victim-btn").addEventListener("click", () => setClickMode("victim"));
  document.getElementById("dispatch-btn").addEventListener("click", runDispatch);
  document.getElementById("clear-dispatch-btn").addEventListener("click", clearFleet);
  document.getElementById("live-start-btn").addEventListener("click", startLiveMode);
  document.getElementById("live-stop-btn").addEventListener("click", stopLiveMode);
  document.getElementById("show-safezones-btn").addEventListener("click", toggleSafeZones);
  document.getElementById("route-safezones-btn").addEventListener("click", routeVictimsToSafeZones);

  connectWebSocket();
  await loadSafeZones();
  await syncLiveStatus();

  log("✅ Connected. Click the map to test routing.");
}

// ---------------------------------------------------------------------------
// Phase 4 — Safe zones
// ---------------------------------------------------------------------------

function safeZoneIcon() {
  return L.divIcon({ html: "🏫", className: "emoji-icon", iconSize: [24, 24] });
}

async function loadSafeZones() {
  try {
    const data = await fetch(`${API}/safezone/list`).then((r) => r.json());
    safeZones = data.zones;
    log(`🏫 ${safeZones.length} safe zone(s) loaded.`);
  } catch (err) {
    log("❌ Could not load safe zones: " + err.message);
  }
}

function toggleSafeZones() {
  safeZonesVisible = !safeZonesVisible;
  safezoneLayer.clearLayers();
  if (safeZonesVisible) {
    safeZones.forEach((z) => {
      L.marker([z.lat, z.lon], { icon: safeZoneIcon() }).addTo(safezoneLayer).bindTooltip(z.name);
    });
    log("🏫 Safe zones shown.");
  } else {
    log("🏫 Safe zones hidden.");
  }
}

async function routeVictimsToSafeZones() {
  if (victims.length === 0) {
    log("⚠️ Place at least one victim before routing to safe zones.");
    return;
  }
  safezoneRouteLayer.clearLayers();
  log(`🏠 Routing ${victims.length} victim(s) to nearest reachable safe zone...`);

  for (let i = 0; i < victims.length; i++) {
    try {
      const res = await fetch(`${API}/safezone/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ victim: victims[i] }),
      });
      const data = await res.json();
      setStat("stat-recompute", data.recompute_ms);

      if (data.all_zones_unreachable) {
        log(`⚠️ Victim ${i + 1}: no reachable safe zone — fully cut off by flooding.`);
        continue;
      }

      L.polyline(data.route_coords, { color: "#ca8a04", weight: 4, dashArray: "2 6" })
        .bindTooltip(`Victim ${i + 1} → ${data.chosen_zone.name} (${data.travel_time_seconds.toFixed(1)}s)`)
        .addTo(safezoneRouteLayer);

      let msg = `🏠 Victim ${i + 1} → ${data.chosen_zone.name}, ${data.travel_time_seconds.toFixed(1)}s`;
      if (data.skipped_zones.length > 0) {
        msg += ` (skipped: ${data.skipped_zones.join(", ")} — flooded out)`;
      }
      log(msg);
    } catch (err) {
      log(`❌ Safe-zone routing failed for victim ${i + 1}: ` + err.message);
    }
  }
}

// ---------------------------------------------------------------------------
// Phase 5 — Live mode (continuous auto flood/recede)
// ---------------------------------------------------------------------------

async function startLiveMode() {
  try {
    const data = await fetch(`${API}/live/start`, { method: "POST" }).then((r) => r.json());
    setLiveStat(data.running);
    log(`▶ Live mode started — ticking every ${data.interval_seconds}s.`);
  } catch (err) {
    log("❌ Could not start live mode: " + err.message);
  }
}

async function stopLiveMode() {
  try {
    const data = await fetch(`${API}/live/stop`, { method: "POST" }).then((r) => r.json());
    setLiveStat(data.running);
    log("⏸ Live mode stopped.");
  } catch (err) {
    log("❌ Could not stop live mode: " + err.message);
  }
}

async function syncLiveStatus() {
  try {
    const data = await fetch(`${API}/live/status`).then((r) => r.json());
    setLiveStat(data.running);
  } catch (err) {
    // non-fatal — just leave the indicator at its default "off" state
  }
}

// ---------------------------------------------------------------------------
// Phase 3 — Fleet placement + dispatch
// ---------------------------------------------------------------------------

function setClickMode(mode) {
  clickMode = mode;
  // Clear any half-finished route click so it doesn't leak into placement mode
  clickPoints = [];
  clickMarkers.forEach((m) => map.removeLayer(m));
  clickMarkers = [];
  log(`📍 Click mode: ${mode}. Click the map to place. Click "Run Dispatch" when ready.`);
}

function vehicleIcon() {
  return L.divIcon({ html: "🚑", className: "emoji-icon", iconSize: [24, 24] });
}

function victimIcon() {
  return L.divIcon({ html: "📍", className: "emoji-icon", iconSize: [24, 24] });
}

function placeVehicle(lat, lng) {
  vehicles.push([lat, lng]);
  vehicleMarkers.push(L.marker([lat, lng], { icon: vehicleIcon() }).addTo(map).bindTooltip(`Vehicle ${vehicles.length}`));
  log(`🚑 Vehicle ${vehicles.length} placed at (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
}

function placeVictim(lat, lng) {
  victims.push([lat, lng]);
  victimMarkers.push(L.marker([lat, lng], { icon: victimIcon() }).addTo(map).bindTooltip(`Victim ${victims.length}`));
  log(`📍 Victim ${victims.length} placed at (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
}

function clearFleet() {
  vehicles = [];
  victims = [];
  vehicleMarkers.forEach((m) => map.removeLayer(m));
  victimMarkers.forEach((m) => map.removeLayer(m));
  vehicleMarkers = [];
  victimMarkers = [];
  dispatchLayer.clearLayers();
  safezoneRouteLayer.clearLayers();
  clickMode = "route";
  log("✕ Fleet cleared.");
}

async function runDispatch() {
  if (vehicles.length === 0 || victims.length === 0) {
    log("⚠️ Place at least one vehicle and one victim before dispatching.");
    return;
  }
  log(`⚡ Dispatching ${vehicles.length} vehicle(s) to ${victims.length} victim(s)...`);
  try {
    await fetch(`${API}/dispatch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vehicles, victims }),
    });
    // Rendering + logging happens via the WebSocket broadcast (renderDispatch),
    // so every connected client sees the same assignment.
  } catch (err) {
    log("❌ Dispatch request failed: " + err.message);
  }
}

function renderDispatch(result) {
  dispatchLayer.clearLayers();
  const { assignments, unreachable, total_travel_time_seconds, dispatch_ms } = result;
  setStat("stat-dispatch", dispatch_ms);

  assignments.forEach((a, idx) => {
    const color = DISPATCH_COLORS[idx % DISPATCH_COLORS.length];
    L.polyline(a.route_coords, { color, weight: 4 })
      .bindTooltip(`Vehicle ${a.vehicle_index + 1} → Victim ${a.victim_index + 1} (${a.travel_time_seconds.toFixed(1)}s)`)
      .addTo(dispatchLayer);
  });

  let msg = `⚡ Dispatch complete — ${assignments.length} assignment(s), ` +
    `total fleet time ${total_travel_time_seconds.toFixed(1)}s, computed in ${dispatch_ms}ms`;
  if (unreachable && unreachable.length > 0) {
    msg += `<br>⚠️ ${unreachable.length} pair(s) unreachable — flooding may have fully cut off a route`;
  }
  log(msg);
}

// ---------------------------------------------------------------------------
// Phase 2 — WebSocket live updates
// ---------------------------------------------------------------------------

function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => setWsStatus(true);
  ws.onclose = () => {
    setWsStatus(false);
    log("⚠️ WebSocket disconnected — retrying in 2s...");
    setTimeout(connectWebSocket, 2000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.type === "flood") {
      drawFloods(msg.events);
      if (msg.events.length > 0) {
        setStat("stat-flood-apply", msg.flood_apply_ms || 0);
        // Live-mode ticks fire up to 5x/sec — logging every single one would
        // flood (pun intended) the log panel, so only log manually-triggered
        // floods verbosely; live ticks get a quieter one-liner.
        if (!msg.live) {
          log(`🌊 ${msg.events.length} flood event(s) — applied in ${msg.flood_apply_ms}ms`);
        }
      }
      scheduleRecompute();
    } else if (msg.type === "recede") {
      removeFloodMarkers(msg.events);
      scheduleRecompute();
    } else if (msg.type === "reset") {
      floodLayer.clearLayers();
      floodMarkersByKey = {};
      log(`↺ Flood state reset (${msg.count} edge(s) restored)`);
      scheduleRecompute();
    } else if (msg.type === "dispatch") {
      renderDispatch(msg);
    }
  };
}

function edgeKey(e) {
  return `${e.u}-${e.v}-${e.k}`;
}

function drawFloods(events) {
  for (const e of events) {
    const key = edgeKey(e);
    // If this exact edge was already flooded (re-flooded to a new depth),
    // remove the old markers first so we don't stack duplicates.
    if (floodMarkersByKey[key]) {
      map.removeLayer(floodMarkersByKey[key].circle);
      map.removeLayer(floodMarkersByKey[key].line);
    }

    const midpoint = [
      (e.coords[0][0] + e.coords[1][0]) / 2,
      (e.coords[0][1] + e.coords[1][1]) / 2,
    ];
    const color = e.impassable ? "#8b0000" : "#e07b00";
    const radius = 4 + Math.min(e.depth_cm / 8, 10);

    const circle = L.circleMarker(midpoint, {
      radius,
      color,
      fillColor: color,
      fillOpacity: 0.7,
      weight: 1,
    })
      .bindTooltip(`${e.depth_cm}cm ${e.impassable ? "(impassable)" : ""}`)
      .addTo(floodLayer);

    const line = L.polyline(e.coords, { color, weight: 4, opacity: 0.6, dashArray: "4 4" }).addTo(floodLayer);

    floodMarkersByKey[key] = { circle, line };
  }
}

function removeFloodMarkers(events) {
  for (const e of events) {
    const key = edgeKey(e);
    const entry = floodMarkersByKey[key];
    if (entry) {
      map.removeLayer(entry.circle);
      map.removeLayer(entry.line);
      delete floodMarkersByKey[key];
    }
  }
}

async function triggerRandomFlood() {
  log("Triggering random flood event...");
  try {
    await fetch(`${API}/flood/random`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n: 5, min_depth: 10, max_depth: 80 }),
    });
    // Actual drawing + logging happens via the WebSocket broadcast above,
    // so every connected client (not just this tab) sees it.
  } catch (err) {
    log("❌ Flood trigger failed: " + err.message);
  }
}

async function triggerReset() {
  log("Resetting flood state...");
  try {
    await fetch(`${API}/flood/reset`, { method: "POST" });
  } catch (err) {
    log("❌ Reset failed: " + err.message);
  }
}

// If a route is currently on screen, recompute it after any flood/reset
// event — this is the "continuous path recalculation" requirement made
// visible: the user doesn't have to click again for the route to update.
//
// THROTTLE, not debounce: Live Mode fires an event every 0.2s. A debounce
// (reset-the-timer-on-every-event) would NEVER fire as long as events keep
// arriving faster than the wait window — the route would freeze in place
// even while flooded edges pile up directly on top of it. A throttle with
// a trailing edge guarantees a recompute happens at least once every
// RECOMPUTE_THROTTLE_MS, no matter how continuously events keep arriving.
function scheduleRecompute() {
  if (!currentRoute.origin || !currentRoute.destination) return;

  const now = Date.now();
  const elapsed = now - lastRecomputeAt;

  const fire = () => {
    lastRecomputeAt = Date.now();
    log("↻ Recomputing current route under new conditions...");
    computeRoute(currentRoute.origin, currentRoute.destination);
  };

  if (elapsed >= RECOMPUTE_THROTTLE_MS) {
    // Quiet long enough (or first event) — recompute right away.
    if (recomputeTrailingTimer) {
      clearTimeout(recomputeTrailingTimer);
      recomputeTrailingTimer = null;
    }
    fire();
  } else if (!recomputeTrailingTimer) {
    // Already recomputed recently — schedule exactly one trailing call for
    // when the current throttle window ends, so a burst of events still
    // results in a recompute instead of being silently swallowed forever.
    recomputeTrailingTimer = setTimeout(() => {
      recomputeTrailingTimer = null;
      fire();
    }, RECOMPUTE_THROTTLE_MS - elapsed);
  }
  // else: a trailing call is already queued — nothing more to do.
}

async function onMapClick(e) {
  const { lat, lng } = e.latlng;

  if (clickMode === "vehicle") {
    placeVehicle(lat, lng);
    return;
  }
  if (clickMode === "victim") {
    placeVictim(lat, lng);
    return;
  }

  // clickMode === "route"
  clickPoints.push([lat, lng]);
  clickMarkers.push(L.marker([lat, lng]).addTo(map));

  if (clickPoints.length === 1) {
    log(`Origin set at (${lat.toFixed(4)}, ${lng.toFixed(4)})`);
    return;
  }

  if (clickPoints.length === 2) {
    const [origin, destination] = clickPoints;
    log("Computing route...");
    await computeRoute(origin, destination);
    // reset for the next click pair
    clickPoints = [];
    clickMarkers.forEach((m) => map.removeLayer(m));
    clickMarkers = [];
  }
}

async function computeRoute(origin, destination) {
  try {
    const res = await fetch(`${API}/route`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ origin, destination }),
    });
    const data = await res.json();
    setStat("stat-recompute", data.recompute_ms);

    routeLayer.clearLayers();
    if (!data.route_coords || data.route_coords.length === 0) {
      log("⚠️ No path found between those points — flooding may have cut off all routes.");
      currentRoute = { origin: null, destination: null };
      return;
    }

    // Remember this route so flood/reset events can trigger a live recompute.
    currentRoute = { origin, destination };

    L.polyline(data.route_coords, { color: "#2b8cbe", weight: 5 }).addTo(routeLayer);

    let msg =
      `✅ Route found — travel time ${data.travel_time_seconds.toFixed(1)}s, ` +
      `recomputed in ${data.recompute_ms} ms`;

    if (data.crosses_flooded_edges && data.crosses_flooded_edges.length > 0) {
      msg += `<br>⚠️ Crosses ${data.crosses_flooded_edges.length} flooded (but passable) edge(s)`;
    }
    log(msg);
  } catch (err) {
    log("❌ Route request failed: " + err.message);
  }
}

init();
