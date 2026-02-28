# Director's Cut — Emotion-Adaptive Film Engine

## What This Is
A hackathon project for Gemini 3 NYC. A short film plays for a viewer. Their webcam captures facial expressions every 8 seconds. Gemini Flash analyzes emotion. A Director Agent (Gemini Pro via LlamaIndex) picks the next story branch. Gemini Flash Image generates scene visuals. Gemini TTS narrates. The viewer gets a personalized film that responds to their reactions.

## Architecture

```
Webcam Frame (every 8s)
    → POST /api/emotion → Gemini 3 Flash → EmotionReading
    → EmotionAccumulator (rolling window of 8 readings)
    → At decision points: POST /api/director/decide
        → Director Agent (Gemini 3 Pro) → SceneDecision
        → POST /api/content/generate (parallel)
            → Gemini 2.5 Flash Image → scene image
            → Gemini 2.5 Flash TTS → narration audio
        → WebSocket pushes SceneAssets to frontend
    → Frontend renders: image + audio + emotion indicator
```

## Tech Stack
- **Backend:** Python 3.12, FastAPI, async throughout
- **Frontend:** Plain HTML/JS/CSS (no React build step — faster for hackathon)
- **Agent Framework:** LlamaIndex Workflows with google-genai SDK
- **All types in:** `backend/app/models.py` (Pydantic v2)
- **Story data in:** `story.json` (static branching graph)
- **Specs in:** `docs/specs/` (one per module)

## Gemini Models & Budget ($25 total)

| Task | Model | Cost/call | Notes |
|---|---|---|---|
| Emotion detection | `gemini-3-flash` | ~$0.0003 | media_resolution: LOW, thinking: NONE, temp: 0.3 |
| Director reasoning | `gemini-3-pro-preview` | ~$0.005 | thinking_level: medium, temp: 0.8 |
| Scene images | `gemini-2.5-flash-image` | $0.039 | 1024px, 16:9. **NEVER use nano-banana-pro** |
| Narration audio | `gemini-2.5-flash-preview-tts` | ~$0.002 | Slow speaking rate for drama |

**~$0.84 per full demo run. Budget for ~18 dev runs + 6 demo runs.**

## CRITICAL RULES
1. **Every Gemini API call** must be wrapped in try/except with a sensible fallback
2. **Unit tests ALWAYS mock** Gemini responses — never burn credits on tests
3. **Type hints everywhere** — no `Any`, no untyped dicts
4. **Implement against the spec** in docs/specs/, not vibes
5. **Image model is always** `gemini-2.5-flash-image` — never the Pro variant
6. **Commit after each working module** via `/commit` command
7. **env vars loaded via** python-dotenv, never hardcoded

## File Map
```
backend/
  app/
    main.py           — FastAPI app, routes, WebSocket, CORS
    models.py          — All Pydantic models (ALREADY WRITTEN — do not change without asking)
    emotion_service.py — M1: webcam frame → EmotionReading
    director_agent.py  — M2: EmotionSummary + StoryState → SceneDecision
    content_pipeline.py— M3: SceneDecision → SceneAssets (image + audio)
    story_engine.py    — M0: loads story.json, manages story state, graph traversal
  tests/
    conftest.py        — shared fixtures, mock helpers
    test_emotion.py
    test_director.py
    test_pipeline.py
    test_story.py
frontend/
  index.html           — single file app with inline JS/CSS
story.json             — branching story graph
docs/specs/            — module specs (source of truth)
```

## Endpoints
```
POST   /api/emotion          — base64 JPEG → EmotionReading
POST   /api/director/decide  — EmotionSummary + StoryState → SceneDecision
POST   /api/content/generate — SceneDecision + SceneData → SceneAssets
GET    /api/story/scene/{id} — SceneData from story.json
GET    /api/story/state      — current StoryState
POST   /api/story/reset      — reset to opening scene
WS     /ws/session           — full loop (receives frames, pushes scenes)
```

## Development Workflow
Spec → Implement → Test (mocked) → Fix → Commit → Next module
Use `/implement`, `/fix`, `/test`, `/commit` commands.

## Parallel Build Strategy
- **Pane 0 (Claude Code):** /implement m0_story.md → /implement m1_emotion.md → /implement m2_director.md
- **Pane 1 (Claude Code):** /implement m3_pipeline.md (independent, run in parallel with M0+M1)
- **Pane 2:** pytest watcher / uvicorn server
