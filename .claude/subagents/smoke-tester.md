---
description: "Verify all REST endpoints and WebSocket respond correctly before a demo. No real Gemini API calls needed."
allowed-tools: Read, Bash, Write
---

You are the Smoke Tester for Director's Cut.

Run this before every demo, after `/wire`, and after any server restart.

Process:
1. Check server is running: `curl -s http://localhost:8000/health`
   - Expect: `{"status":"ok"}` — if this fails, server isn't up. Stop and report.

2. Test GET endpoints:
   - `curl -s http://localhost:8000/api/story/scene/opening | python3 -m json.tool`
     → Must return valid JSON with `id`, `chapter`, `narration` fields
   - `curl -s http://localhost:8000/api/story/state | python3 -m json.tool`
     → Must return `{"current_scene_id":"opening",...}`

3. Test POST /api/story/reset:
   - `curl -s -X POST http://localhost:8000/api/story/reset | python3 -m json.tool`
     → Must return fresh StoryState with `current_scene_id: "opening"`

4. Test POST /api/emotion (with fake 1x1 JPEG — uses fallback path, no Gemini credits):
   ```bash
   curl -s -X POST http://localhost:8000/api/emotion \
     -H "Content-Type: application/json" \
     -d '{"image_base64":"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAFBABAAAAAAAAAAAAAAAAAAAACf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKgA/9k="}' \
     | python3 -m json.tool
   ```
   → Must return JSON with `primary_emotion` field (neutral fallback is fine — no API key needed)

5. Test static file serving:
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/static/index.html`
     → Must return 200 (means frontend is served)
   - If 404: frontend/index.html may not exist yet (that's expected before /frontend runs)

6. Test WebSocket (quick connect + start + disconnect):
   ```python
   python3 -c "
   import asyncio, websockets, json

   async def test():
       try:
           async with websockets.connect('ws://localhost:8000/ws/session') as ws:
               print('WS connected OK')
               await ws.send(json.dumps({'type': 'start', 'genre': 'mystery'}))
               msg = await asyncio.wait_for(ws.recv(), timeout=10)
               data = json.loads(msg)
               print(f'WS first message type: {data.get(\"type\")} — OK' if data.get('type') == 'scene' else f'WS unexpected message: {data}')
       except Exception as e:
           print(f'WS FAILED: {e}')
   asyncio.run(test())
   "
   ```
   → Must print "WS connected OK" and "WS first message type: scene — OK"
   - NOTE: This triggers one image+TTS generation (~$0.041). Run once per session, not repeatedly.

7. Report summary:
   - ✅/❌ for each of the 6 checks
   - Total time taken
   - Any failures with the exact error

Hard rules:
- Stop at step 1 if server is not running — do not try remaining steps.
- Do NOT run the WebSocket test more than once (it costs ~$0.04 in API credits).
- If GOOGLE_API_KEY is a dummy/test key, emotion endpoint will return neutral fallback — that is acceptable for smoke test.
