Run an end-to-end integration test with REAL Gemini API calls.
WARNING: This burns API credits (~$0.84 per run). Only run after all unit tests pass.

Process:
1. Verify all unit tests pass first: cd backend && python -m pytest tests/ -v
2. If any fail, STOP and fix them first
3. Verify GOOGLE_API_KEY is set in .env (not the placeholder)
4. Start backend: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &
5. Wait 3 seconds for startup
6. Test each endpoint with real data:
   a. POST /api/story/reset → verify StoryState returned
   b. GET /api/story/scene/opening → verify SceneData
   c. POST /api/emotion with a test image → verify EmotionReading
   d. POST /api/director/decide with test data → verify SceneDecision
   e. POST /api/content/generate → verify SceneAssets (this calls real image gen + TTS)
7. Kill the server
8. Report: which endpoints work, which fail, estimated cost
