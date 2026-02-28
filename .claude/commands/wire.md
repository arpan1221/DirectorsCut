Wire all implemented modules together in backend/app/main.py.

Process:
1. Read ALL implementations: emotion_service.py, director_agent.py, content_pipeline.py, story_engine.py
2. Read CLAUDE.md for endpoint definitions
3. Create the FastAPI app in main.py with:
   - CORS middleware (allow all origins for hackathon)
   - Static file serving for frontend/
   - All REST endpoints from CLAUDE.md
   - WebSocket endpoint /ws/session that orchestrates the full loop
   - Startup event that loads story.json and initializes genai client
4. The WebSocket handler should:
   - Accept connection
   - On "start" message: reset story state, send opening scene assets
   - On "frame" message: analyze emotion, add to accumulator, check if decision needed,
     if at decision point run director + content pipeline, send new scene
   - On "reset": reset state
5. Run: cd backend && python -m pytest tests/ -v (ensure nothing broke)
6. Start server and verify: curl http://localhost:8000/api/story/scene/opening
