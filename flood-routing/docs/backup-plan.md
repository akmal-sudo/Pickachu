# Backup Plan

Live demos fail for boring reasons — bad wifi, projector HDMI, a laptop
falling asleep. This is not a reflection on the project. Plan for it.

## Before the event (do this the night before, not the morning of)

1. **Record a backup video.** Screen-record the full pitch-script.md
   sequence end-to-end, narrated, on a laptop with the backend already
   fully warmed up (graph loaded, cache populated). 3–4 minutes is fine.
   Export as .mp4, put it on the presenting laptop's desktop AND on a USB
   stick AND on a phone. Three copies, not one.
2. **Pre-warm the OSM cache.** Run the app once fully through the whole
   demo sequence beforehand so `backend/cache/` is populated — this makes
   graph loading on demo day near-instant even if venue wifi is bad,
   since `osmnx` will hit the local cache instead of the network for
   anything already fetched.
3. **Test on the actual venue wifi if at all possible.** Corporate/event
   wifi often blocks non-standard ports or has aggressive firewalls —
   confirm `localhost:8000` and the WebSocket both work on the network
   you'll actually be presenting on, not just at home.
4. **Charge everything. Bring your own HDMI/USB-C adapter.** Don't rely on
   the venue having the right one.

## Fallback ladder (use the first one that still works)

1. **Full live demo** — the default plan.
2. **Live demo, but skip live-mode ticking if wifi is laggy** — the core
   click-to-route + Simulate Flood + Dispatch story still lands fine
   without Phase 5's auto-ticking; it's the least essential piece to cut
   under time or connectivity pressure.
3. **Backup video, played straight through, live narration on top.** Don't
   apologize extensively — say "we've got this running live in the video,
   let me walk you through it" and keep energy up.
4. **Backup video, pre-recorded narration (no live mic needed)** — the
   last resort if something's wrong with your own voice/mic setup too.

## Things NOT to do if something breaks

- Don't debug backend errors on stage — switch to the backup video instead
  of losing 90 seconds staring at a traceback.
- Don't restart the whole app and wait for OSM to redownload — if cache
  isn't warmed, that can take 30+ seconds you don't have.
- Don't skip straight to Q&A out of frustration — the video still tells the
  story even if you didn't get to click through it live.
