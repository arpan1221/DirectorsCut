---
description: "Replay a WebSocket session with fake frames and print full message trace. Use when frontend shows blank screen, WS drops immediately, or scenes don't advance."
allowed-tools: Read, Write, Bash
---

You are the WebSocket Debugger for Director's Cut.

Trigger when: frontend is blank after Start, WS disconnects immediately, scenes stop advancing, or "deciding" overlay never clears.

Process:
1. Read `backend/app/main.py` — trace the WebSocket handler logic, particularly:
   - How sessions are stored (sessions dict keyed by id(websocket))
   - The frame_count / frames_needed advancement logic
   - Decision point detection
   - How messages are serialized (model_dump() for SceneAssets)

2. Check the most common failure modes before running the debug script:
   - Is `story_data` empty? (happens if lifespan didn't load story.json)
   - Is the path to story.json correct? (should be 3 dirs up from main.py)
   - Does SceneAssets serialize correctly with None fields?
   - Is the WS session being cleaned up on disconnect correctly?

3. Write this debug script to `/tmp/ws_debug.py`:
```python
import asyncio
import json
import base64

# 1x1 white pixel JPEG (same as conftest.py fake_frame_base64)
FAKE_FRAME = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAFBABAAAAAAAAAAAAAAAAAAAACf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKgA/9k="

async def main():
    import websockets

    print("Connecting to ws://localhost:8000/ws/session ...")
    try:
        async with websockets.connect("ws://localhost:8000/ws/session") as ws:
            print("✅ Connected")

            # Send start
            await ws.send(json.dumps({"type": "start", "genre": "mystery"}))
            print("→ Sent: {type: start}")

            # Listen for first scene (may take a few seconds for generation)
            print("Waiting for opening scene (up to 30s — image+TTS generation)...")
            msg1 = await asyncio.wait_for(ws.recv(), timeout=30)
            data1 = json.loads(msg1)
            print(f"← Received: type={data1.get('type')}")
            if data1.get("type") == "scene":
                assets = data1.get("assets", {})
                print(f"   scene_id: {assets.get('scene_id')}")
                print(f"   has image: {assets.get('image_base64') is not None}")
                print(f"   has audio: {assets.get('audio_base64') is not None}")
                print(f"   narration: {assets.get('narration_text', '')[:60]}...")
            else:
                print(f"   UNEXPECTED: {data1}")

            # Send 3 fake frames spaced 1s apart
            for i in range(3):
                await asyncio.sleep(1)
                await ws.send(json.dumps({"type": "frame", "data": FAKE_FRAME}))
                print(f"→ Sent: frame {i+1}/3")

                # Collect any messages that arrive
                try:
                    while True:
                        resp = await asyncio.wait_for(ws.recv(), timeout=3)
                        data = json.loads(resp)
                        print(f"← Received: type={data.get('type')} | {str(data)[:100]}")
                except asyncio.TimeoutError:
                    pass  # no more messages right now

            print("\n✅ Debug session complete")
    except ConnectionRefusedError:
        print("❌ Connection refused — is uvicorn running on port 8000?")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")

asyncio.run(main())
```

4. Run: `cd /path/to/worktree && source backend/.venv/bin/activate && python3 /tmp/ws_debug.py`

5. Analyze the output:
   - If "Connection refused" → server isn't running
   - If connected but no scene after 30s → check content_pipeline, check GOOGLE_API_KEY
   - If scene arrives but image_base64 is None → image generation failing (check model name)
   - If frame messages don't trigger scene advances → check frame_count / frames_needed logic
   - If WS drops immediately → check for exception in the ws handler before the message loop

6. Report:
   - Full message trace with timestamps
   - Identified failure point (file + line if possible)
   - Suggested fix (one-liner if possible)

Hard rules:
- Running this script will trigger real API calls if GOOGLE_API_KEY is real (~$0.04 for opening scene).
- Don't run more than twice in a session.
- If you find a code bug, fix it yourself and then re-run once to verify.
