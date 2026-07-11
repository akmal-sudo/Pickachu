# Flood-Aware Evacuation Routing

Real-time flood-aware rescue routing and fleet dispatch. Built phase by
phase — see `docs/phase-plan.md` for the full roadmap and what maps to
which problem-statement requirement.

## Phase 1 Setup (VS Code)

### 1. Open the project
`File → Open Folder` → select this `flood-routing` folder.

### 2. Open the integrated terminal
`` Ctrl+` `` (backtick).

### 3. Create and activate a virtual environment
```bash
python3 -m venv venv
```
- Mac/Linux: `. venv/bin/activate`
- Windows PowerShell: `venv\Scripts\Activate.ps1`

Confirm the Python interpreter selector (bottom-right of VS Code) points to
`./venv`.

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Set your demo area
Edit `backend/config.py`, change `PLACE_NAME` to a small real place (a
neighborhood/district — keep it small so the OSM download and demo stay
fast).

### 6. Run the backend
```bash
cd backend
uvicorn app:app --reload --port 8000
```
Or press **F5** in VS Code (uses `.vscode/launch.json`, already configured).

Wait for `[startup] Graph ready: {...}` in the terminal. Then check
`http://localhost:8000/health` in a browser — should say `"status": "ready"`.

### 7. Open the frontend
Open `frontend/index.html` directly in a browser (double-click it, or use
the Live Server extension). Click two points on the map — a route should
draw, and the log panel should show a recompute time in milliseconds.

### 8. Run tests
```bash
cd backend
python -m pytest tests/ -v
```
All 3 tests should pass. These don't need internet — they run against a
small hand-built graph, so you can sanity-check the routing logic anytime.

## Definition of Done for Phase 1

- [ ] `/health` returns `"status": "ready"`
- [ ] Clicking two points on the map draws a route
- [ ] Recompute time is logged and reasonable (well under 1 second)
- [ ] `pytest` passes all tests

Once all four are true, move to Phase 2 — see `docs/phase-plan.md`.

## Git

Not initialized yet, per your plan to push later. When ready:
```bash
git init
git add .
git commit -m "Phase 1: core routing engine"
```
Commit at the end of every phase — gives you working checkpoints to roll
back to if a later phase breaks something.
