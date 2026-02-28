---
description: "Check if uvicorn is running, validate .env and venv state, open the frontend in browser. Use at the start of each coding session."
allowed-tools: Read, Bash
---

You are the Dev Server assistant for Director's Cut.

Run at the start of every coding session, or when someone asks "how do I start the server?"

Process:
1. Check if uvicorn is already running:
   ```bash
   lsof -i :8000 | grep LISTEN
   ```
   - If output shows a process: server is UP → go to step 5
   - If empty: server is DOWN → continue to step 2

2. Check that the venv exists:
   ```bash
   ls backend/.venv/bin/activate
   ```
   - If missing: tell user to run:
     `python3.12 -m venv backend/.venv && source backend/.venv/bin/activate && pip install -r backend/requirements.txt`

3. Check that `.env` has a real API key (without printing it):
   ```bash
   grep -q "GOOGLE_API_KEY=.\{10,\}" .env && echo "KEY_SET" || echo "KEY_MISSING_OR_PLACEHOLDER"
   ```
   - If KEY_MISSING_OR_PLACEHOLDER: warn user to add their Gemini API key to .env before running /e2e

4. Check story.json exists at repo root:
   ```bash
   ls story.json && echo "FOUND" || echo "MISSING"
   ```
   - If missing: tell user story.json needs to be present (should have been committed in Phase 0)

5. Print the exact command to start the server:
   ```
   ┌─────────────────────────────────────────────────────────────┐
   │  Run this in a SEPARATE terminal pane (not this one):       │
   │                                                             │
   │  cd /Users/arpannookala/Documents/DirectorsCut/             │
   │      .claude/worktrees/epic-haslett                         │
   │  source backend/.venv/bin/activate                          │
   │  cd backend && uvicorn app.main:app --reload --port 8000    │
   │                                                             │
   │  Then come back here and continue.                          │
   └─────────────────────────────────────────────────────────────┘
   ```

6. If server is already UP (detected in step 1):
   - Open the frontend: `open http://localhost:8000/static/index.html`
   - If that 404s (frontend not built yet): `open frontend/index.html` directly
   - Print: "Server is running. Frontend opened in browser."

7. Print a quick-reference card:
   ```
   ┌── Quick Reference ─────────────────────────────────────────┐
   │  Server:    http://localhost:8000                           │
   │  Health:    curl http://localhost:8000/health               │
   │  Scene:     curl http://localhost:8000/api/story/scene/opening │
   │  Frontend:  http://localhost:8000/static/index.html        │
   │  Tests:     cd backend && python -m pytest tests/ -v       │
   │  Budget:    use smoke-tester or budget-tracker subagent    │
   └────────────────────────────────────────────────────────────┘
   ```

Hard rules:
- Never print the contents of .env.
- Never start uvicorn yourself — only print the command for the user to run in their own terminal.
- If venv is missing, stop at step 2 and wait for user to create it.
