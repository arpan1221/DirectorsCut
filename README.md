# Director's Cut

> An adaptive short film that reshapes itself around your emotions in real time.

Built for the **Gemini 3 NYC Hackathon**. A mystery film plays while your webcam watches you. Every 10 seconds Gemini analyzes your face. A Director Agent reads your emotion history and picks the next story branch. Scene visuals and narration are generated on the fly — uniquely yours, every run.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (Netlify)                               │
│                                                                              │
│  ┌─────────┐  frame every 10s  ┌───────────────────────────────────────┐   │
│  │ Webcam  │──────────────────▶│  Gemini Live API  (client-side)       │   │
│  └─────────┘                   │  emotion detection, real-time         │   │
│       │ (fallback when         └────────────────┬──────────────────────┘   │
│       │  Gemini Live unavail.)                  │ EmotionReading            │
│       │                                         ▼                          │
│       │                         ┌───────────────────────────────────────┐  │
│       └────────────────────────▶│  useBackendWS  (wss://railway-url)    │  │
│         raw frame relay         │  reconnects automatically, 2.5s delay │  │
│                                 └────────────────┬──────────────────────┘  │
│                                                  │ SceneAssets              │
│                                                  ▼                          │
│                                 ┌───────────────────────────────────────┐  │
│                                 │  React App                            │  │
│                                 │  • Scene image / Veo video            │  │
│                                 │  • TTS narration audio                │  │
│                                 │  • Emotion dial + history             │  │
│                                 │  • Story map + ending screen          │  │
│                                 └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                          │  WebSocket  /ws/session
                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI BACKEND (Railway)                          │
│                                                                              │
│  WebSocket handler receives:  "start" | "frame" | "emotion" | "reset"       │
│                                                                              │
│  "frame" path                          "emotion" path                        │
│  ─────────────────────                 ──────────────────────────────        │
│  Gemini 2.5 Flash                      EmotionReading arrives pre-computed   │
│  analyzes JPEG → EmotionReading        (from Gemini Live in browser)         │
│                  │                                       │                   │
│                  └──────────────┬────────────────────────┘                  │
│                                 ▼                                            │
│                    ┌────────────────────────┐                               │
│                    │   EmotionAccumulator   │                               │
│                    │   rolling window of 8  │                               │
│                    └───────────┬────────────┘                               │
│                                │  at decision point                         │
│                                ▼                                            │
│               ┌────────────────────────────────┐                           │
│               │  Director Agent (LlamaIndex)   │                           │
│               │  gemini-2.5-flash              │                           │
│               │  emotion → branch selection    │                           │
│               └──────────────┬─────────────────┘                           │
│                              │ SceneDecision                                │
│                              ▼                                              │
│               ┌────────────────────────────────┐                           │
│               │  Narrator Agent (LlamaIndex)   │                           │
│               │  gemini-2.5-flash              │                           │
│               │  adapts narration text to      │                           │
│               │  viewer's emotion + genre      │                           │
│               └──────────────┬─────────────────┘                           │
│                              │ override_narration                           │
│                              ▼                                              │
│               ┌────────────────────────────────┐                           │
│               │  Content Pipeline  (parallel)  │                           │
│               │                                │                           │
│               │  Image:  gemini-2.5-flash-image│                           │
│               │  Audio:  gemini-2.5-pro-tts    │                           │
│               │  Video:  veo-3.0 (demo only)   │                           │
│               └──────────────┬─────────────────┘                           │
│                              │ SceneAssets (image/video + audio + text)     │
│                              ▼                                              │
│                    WS push → browser                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### AI Mode indicator (bottom-right of UI)

| Mode | Meaning |
|------|---------|
| **Live** | Gemini Live API connected — emotion detected client-side, streamed to backend |
| **Relay** | Fallback — webcam frames sent to backend for server-side Gemini analysis |
| **Off** | No connection; story still advances using synthetic neutral readings |

---

## AI Pipeline

| Stage | Model | Fires when | Cost/call |
|-------|-------|-----------|-----------|
| Emotion detection (relay) | `gemini-2.5-flash` | Every frame when Gemini Live is off | ~$0.0003 |
| Director Agent | `gemini-2.5-flash` | 3× per run (at each decision point) | ~$0.001 |
| Narrator Agent | `gemini-2.5-flash` | Every scene transition | ~$0.001 |
| Scene image | `gemini-2.5-flash-image` | Every scene (~7 scenes per run) | ~$0.039 |
| TTS narration | `gemini-2.5-pro-preview-tts` | Every scene | ~$0.003 |
| Scene video | `veo-3.0-generate-001` | Demo only (`VEO_ENABLED=true`) | $0.90/scene |

**~$0.45 per full run (image mode). Keep `VEO_ENABLED=false` for development.**

---

## Story Structure

The film has 3 decision points with 5 possible endings. The Director Agent maps your dominant emotion to a branch at each fork.

```
opening ──▶ foyer ──▶ sound_upstairs ──▶ [DECISION 1]
                                              │
                   engaged/tense/surprised ──▶│──▶ upstairs_door ──▶ study_reveal ──▶┐
                   bored/neutral           ──▶│──▶ figure_appears ──▶ hidden_room ───▶│
                   confused               ──▶│──▶ foyer_detail ──▶ upstairs_door ───▶│
                                              │                                        │
                                              └────────────────────────────────────────┘
                                                                    │
                                                              [DECISION 2]
                                                                    │
                              engaged/tense/surprised ─────────────▶│──▶ conspiracy_deep ──▶┐
                              bored/neutral ───────────────────────▶│──▶ twist_reveal ──────▶│
                              amused ────────────────────────────── ▶│──▶ dark_humor_beat ───▶│
                              confused ──────────────────────────── ▶│──▶ narrator_explains ─▶│
                                                                    │                         │
                                                                    └─────────────────────────┘
                                                                                │
                                                                          [DECISION 3]
                                                                                │
                                                   engaged ─────────────────── ▶ ending_solve
                                                   tense/neutral ───────────── ▶ ending_bittersweet
                                                   surprised/bored ──────────  ▶ ending_twist
                                                   amused ─────────────────── ▶ ending_humorous
                                                   confused ──────────────────▶ ending_supernatural
```

Each run produces a unique path through **4–7 scenes** depending on pacing. All 5 genres (Mystery, Thriller, Horror, Sci-Fi) share the same scene graph; the Director and Narrator agents adapt tone per genre.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite |
| Backend | Python 3.12, FastAPI, asyncio |
| Agent framework | LlamaIndex Workflows |
| AI SDK | `google-genai` Python SDK, `@google/genai` JS SDK |
| Data validation | Pydantic v2 |
| Local dev | Docker Compose + nginx reverse proxy |
| Frontend hosting | Netlify |
| Backend hosting | Railway |

---

## Local Development

**Prerequisites:** Docker Desktop, a Gemini API key.

```bash
cp .env.example .env
# Edit .env — fill in GOOGLE_API_KEY

docker compose up --build
```

Open **http://localhost:3000**. The nginx proxy forwards `/api/` and `/ws/` to the FastAPI container. `VITE_BACKEND_URL` is not set, so the frontend connects same-origin.

### Frontend hot-reload (optional)

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173 — set VITE_BACKEND_URL=http://localhost:8000 in .env.local
```

---

## Deployment

### Railway (backend)

1. Connect repo in Railway → set root as build context
2. Railway auto-detects `railway.toml` and builds from `backend/Dockerfile`
3. Set env vars in Railway UI:

```
GOOGLE_API_KEY=...
CORS_ALLOWED_ORIGINS=https://<your-site>.netlify.app
```

Railway injects `$PORT` at runtime; the Dockerfile uses `${PORT:-8000}` as fallback.

### Netlify (frontend)

1. Connect repo in Netlify → it auto-reads `netlify.toml` (base: `frontend/`, publish: `dist/`)
2. Set env vars in Netlify UI:

```
VITE_GEMINI_API_KEY=...
VITE_BACKEND_URL=https://<your-railway-app>.up.railway.app
```

Vite bakes `VITE_*` vars into the JS bundle at build time. The `VITE_BACKEND_URL` tells the browser to open the WebSocket directly to Railway, bypassing Netlify (which cannot proxy WebSocket connections).

### Sequence

```
1. Push branch
2. Railway deploys backend → copy Railway URL
3. Create Netlify site → set VITE_BACKEND_URL + VITE_GEMINI_API_KEY → deploy
4. Copy Netlify URL → update CORS_ALLOWED_ORIGINS in Railway → Railway restarts
```

---

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `GOOGLE_API_KEY` | Railway (backend) | All server-side Gemini calls |
| `CORS_ALLOWED_ORIGINS` | Railway (backend) | Comma-separated list of allowed frontend origins |
| `VITE_GEMINI_API_KEY` | Netlify (frontend build) | Gemini Live API in the browser |
| `VITE_BACKEND_URL` | Netlify (frontend build) | Railway backend URL; absent = same-origin fallback |
| `VEO_ENABLED` | Railway (backend) | `true` only for live demo — generates Veo video per scene |

See `.env.example` for a template.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, REST endpoints, WebSocket /ws/session
│   │   ├── models.py            # All Pydantic models (source of truth)
│   │   ├── story_engine.py      # Loads story.json, manages state and graph traversal
│   │   ├── emotion_service.py   # Webcam frame → EmotionReading (Gemini Flash)
│   │   ├── director_agent.py    # EmotionSummary → SceneDecision (LlamaIndex + Gemini)
│   │   ├── narrator_agent.py    # Adapts narration text to viewer emotion (LlamaIndex)
│   │   └── content_pipeline.py # SceneDecision → image + audio + optional video
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main React component — UI, state machine, event loop
│   │   ├── StoryMap.tsx         # Visual story progress component
│   │   ├── types.ts             # Shared TypeScript types
│   │   └── hooks/
│   │       ├── useBackendWS.ts  # WebSocket client with auto-reconnect
│   │       ├── useCamera.ts     # Webcam capture hook
│   │       └── useGeminiLive.ts # Gemini Live API hook (client-side emotion detection)
│   └── vite.config.ts
├── docs/specs/                  # Module specs (source of truth for AI impl)
├── story.json                   # Branching story graph — scenes, narration, image prompts
├── docker-compose.yml
├── nginx.conf
├── netlify.toml                 # Netlify build config
├── railway.toml                 # Railway build + healthcheck config
└── .env.example
```
