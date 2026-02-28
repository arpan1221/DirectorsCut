# Director's Cut — Full Setup (6 Hours, Solo, Claude Max)

> Run every command in this doc top to bottom. Everything is copy-paste ready.
> You have Claude Max so token budget is unlimited for dev — the $25 constraint is Gemini API credits only.

---

## PHASE 1: REPO SCAFFOLD (10 minutes)

```bash
mkdir directors-cut && cd directors-cut
git init

# Backend structure
mkdir -p backend/app backend/tests docs/specs

# Frontend structure  
mkdir -p frontend/src frontend/public

# Claude Code config
mkdir -p .claude/commands .claude/subagents .claude/skills

# Create all files
touch backend/app/__init__.py
touch backend/app/main.py
touch backend/app/models.py
touch backend/app/emotion_service.py
touch backend/app/director_agent.py
touch backend/app/content_pipeline.py
touch backend/app/story_engine.py
touch backend/tests/__init__.py
touch backend/tests/test_emotion.py
touch backend/tests/test_director.py
touch backend/tests/test_pipeline.py
touch backend/tests/conftest.py
touch story.json
touch .env
touch .gitignore
```

### .gitignore
```bash
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
.env
.venv/
node_modules/
dist/
.DS_Store
*.egg-info/
.pytest_cache/
EOF
```

### backend/requirements.txt
```bash
cat > backend/requirements.txt << 'EOF'
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-dotenv>=1.0.0
google-genai>=1.0.0
llama-index-core>=0.12.0
llama-index-llms-google-genai>=0.4.0
pydantic>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
httpx>=0.27.0
pillow>=10.0.0
python-multipart>=0.0.9
websockets>=13.0
EOF
```

### .env
```bash
cat > .env << 'EOF'
GOOGLE_API_KEY=paste-your-key-here
EOF
```

### Install and verify
```bash
python3 -m venv .venv
source .venv/bin/activate
cd backend && pip install -r requirements.txt && cd ..
```

---

## PHASE 2: CLAUDE.md (The Master Brain)

```bash
cat > CLAUDE.md << 'CLAUDEMD'
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
CLAUDEMD
```

---

## PHASE 3: MODULE SPECS

### docs/specs/m0_story.md
```bash
cat > docs/specs/m0_story.md << 'EOF'
# M0: Story Engine

## Purpose
Loads story.json, manages story state, provides graph traversal.

## Input/Output
- `load_story(path: str) -> dict` — load and validate story.json
- `get_scene(scene_id: str) -> SceneData` — return a scene by ID
- `get_branches(decision_id: str) -> dict[str, str]` — return adaptation_rules for a decision point
- `advance(story_state: StoryState, next_scene_id: str) -> StoryState` — update state

## StoryState (from models.py)
Tracks: current_scene_id, scenes_played list, current_chapter, genre

## story.json format
```json
{
  "title": "The Inheritance",
  "genre": "mystery",
  "scenes": {
    "scene_id": {
      "id": "scene_id",
      "chapter": "Chapter Name",
      "image_prompt": "Cinematic film still...",
      "narration": "The narrator says...",
      "duration_seconds": 16,
      "next": "next_scene_id or null",
      "is_decision_point": false,
      "adaptation_rules": null
    }
  }
}
```

For decision points: `is_decision_point: true`, `next: null`, and `adaptation_rules` maps emotion states to scene IDs:
```json
{
  "adaptation_rules": {
    "engaged": "scene_a",
    "tense": "scene_a",
    "bored": "scene_b",
    "neutral": "scene_b",
    "confused": "scene_c",
    "default": "scene_a"
  }
}
```

## Error Handling
- Missing scene_id → raise ValueError
- Invalid story.json → raise on startup, don't silently fail
EOF
```

### docs/specs/m1_emotion.md
```bash
cat > docs/specs/m1_emotion.md << 'EOF'
# M1: Emotion Service

## Purpose
Takes a webcam frame (base64 JPEG), sends to Gemini 3 Flash for facial expression analysis, returns structured EmotionReading. Also maintains an EmotionAccumulator for smoothing.

## analyze_frame(frame_base64: str) -> EmotionReading

### Gemini Call
- Model: `gemini-3-flash`
- Input: the image as base64 with this prompt:
```
Analyze this webcam image of a person watching a film.
Return ONLY a JSON object with these exact fields:
{
  "primary_emotion": one of "engaged","bored","confused","amused","tense","surprised","neutral",
  "intensity": integer 1-10,
  "attention": one of "screen","away","uncertain",
  "confidence": float 0.0-1.0
}
No other text. Only the JSON object.
```
- Settings: media_resolution=low, thinking_level=none, temperature=0.3
- Parse the JSON response into an EmotionReading (Pydantic model)

### Error handling
- If Gemini returns invalid JSON → return EmotionReading with primary_emotion="neutral", intensity=5, confidence=0.0
- If API call fails (timeout, rate limit) → same fallback
- Log all errors but never crash

## EmotionAccumulator class

### State
- `history: list[EmotionReading]` — rolling window, max 8 entries
- `baseline: EmotionReading | None` — set from first frame (calibration)

### Methods
- `add_reading(reading: EmotionReading)` — append, trim to 8
- `get_summary() -> EmotionSummary`:
  - `dominant_emotion`: mode of primary_emotions in window
  - `trend`: compare avg intensity of last 3 vs first 3 — "rising"/"falling"/"stable" (threshold: ±1.5)
  - `intensity_avg`: mean of intensities
  - `attention_score`: fraction with attention=="screen"
  - `volatility`: std dev of intensities
  - `reading_count`: len(history)
- `should_trigger() -> bool`:
  - True if 3+ consecutive same emotion
  - OR intensity spike >4 from baseline
  - OR attention_score < 0.5
  - OR reading_count >= 3 (minimum data)
  - False if reading_count < 3
EOF
```

### docs/specs/m2_director.md
```bash
cat > docs/specs/m2_director.md << 'EOF'
# M2: Director Agent

## Purpose
The creative brain. Takes EmotionSummary + StoryState, decides which scene to play next at decision points. Uses Gemini 3 Pro for reasoning.

## decide(emotion_summary: EmotionSummary, story_state: StoryState, story_data: dict) -> SceneDecision

### Logic
1. Get current scene from story_state.current_scene_id
2. Find the next node (scene.next)
3. If next node is NOT a decision point → return SceneDecision(next_scene_id=next.id) directly, no Gemini call needed
4. If next node IS a decision point:
   a. Get adaptation_rules from the decision point
   b. Map emotion_summary.dominant_emotion to a branch via adaptation_rules
   c. If no match → use "default" key
   d. Call Gemini 3 Pro with context for creative reasoning about the choice

### Gemini Call (only at decision points)
- Model: `gemini-3-pro-preview`
- System prompt: see below
- Temperature: 0.8
- thinking_level: medium

System prompt:
```
You are the Director of an adaptive mystery film called "The Inheritance".
You are making a narrative decision based on the viewer's emotional state.

Story so far: {scenes_played as brief summary}
Current viewer state: {emotion_summary}
Available branches: {adaptation_rules}

Pick the best branch for this viewer. Return ONLY JSON:
{
  "next_scene_id": "the scene id you choose",
  "mood_shift": "tense" or "warm" or "mysterious" or null,
  "pacing": "slow" or "medium" or "fast",
  "reasoning": "One sentence explaining your choice"
}
```

### Error handling
- If Gemini call fails → use the simple mapping (dominant_emotion → adaptation_rules) without reasoning
- If mapped scene doesn't exist → use "default" branch
- Never crash, always return a valid SceneDecision

### Important
- Do NOT call Gemini Pro for non-decision-point transitions. Just return the next scene directly. This saves budget.
- Each Gemini Pro call costs ~$0.005. Budget allows ~40 total calls. Only 3-4 per demo run.
EOF
```

### docs/specs/m3_pipeline.md
```bash
cat > docs/specs/m3_pipeline.md << 'EOF'
# M3: Content Pipeline

## Purpose
Takes a SceneDecision + SceneData, generates the scene image and narration audio in parallel. Returns SceneAssets.

## generate_scene(decision: SceneDecision, scene: SceneData) -> SceneAssets

### Image Generation
- Model: `gemini-2.5-flash-image`
- Prompt: scene.image_prompt (already includes style direction)
  - If decision.mood_shift is set, append: "Mood: {mood_shift}"
- Output: base64 encoded image string
- Settings: aspect_ratio 16:9, output resolution 1024

### TTS Narration
- Model: `gemini-2.5-flash-preview-tts`
- Input text: decision.override_narration or scene.narration
- Voice: pick a deep, dramatic male voice for mystery genre
- Output: base64 encoded audio

### Parallel execution
- Use asyncio.gather to run image gen and TTS concurrently
- Both are independent — if one fails, still return the other

### Caching
- Maintain a dict[str, SceneAssets] keyed by scene_id
- Before generating, check cache. If hit, return cached version.
- This prevents re-generating the same scene and saves ~$0.04 per cache hit.

### Pre-generation
- `pregenerate_branches(decision_point: SceneData, story_data: dict) -> None`
- For each possible branch target in adaptation_rules.values():
  - Get the scene data
  - Call generate_scene in background
  - Store in cache
- This runs WHILE the current scene is playing, so the next scene is instant

### Error handling
- Image gen fails → return SceneAssets with image_base64=None (frontend shows narration-only)
- TTS fails → return SceneAssets with audio_base64=None (frontend shows text subtitle only)
- Both fail → return SceneAssets with just narration_text (degraded but functional)
- Log all errors, never crash

### Cost control
- ALWAYS use gemini-2.5-flash-image, NEVER gemini-3-pro-image-preview
- Check cache before every generation
- Pre-gen max 2 branches (not all possible future scenes)
EOF
```

### docs/specs/m4_frontend.md
```bash
cat > docs/specs/m4_frontend.md << 'EOF'
# M4: Frontend

## Purpose
Single-page app. Displays the film experience: scene image, narration audio, webcam preview, emotion indicator, story metadata. Communicates with backend via REST + WebSocket.

## Tech
- Single index.html with inline CSS and JS (no build step)
- No React, no npm, no bundler — just vanilla HTML/JS/CSS
- Served by FastAPI as a static file

## Layout
```
┌───────────────────────────────────────────────────┐
│  DIRECTOR'S CUT          [Genre: Mystery]          │
├───────────────────────────────────────────────────┤
│                                    ┌─────────────┐│
│                                    │ 📷 Webcam   ││
│   ┌──────────────────────────┐     │  (200x150)  ││
│   │                          │     ├─────────────┤│
│   │    SCENE IMAGE           │     │ 😊 Engaged  ││
│   │    (fills main area)     │     │ Intensity: 7││
│   │                          │     │ ████████░░  ││
│   └──────────────────────────┘     └─────────────┘│
│                                                    │
│   "The door creaked open, revealing a room..."     │
│                                                    │
│   Ch: The Arrival  |  Scene 3/12  |  🎭 Mysterious│
├───────────────────────────────────────────────────┤
│  [ ▶ Start ]  [ 🎬 Pick Genre ]  [ ⟳ Reset ]     │
└───────────────────────────────────────────────────┘
```

## Webcam
- Use navigator.mediaDevices.getUserMedia({video: true})
- Small preview element top-right (200x150)
- Every 8 seconds: capture frame to canvas → toDataURL('image/jpeg', 0.7) → strip prefix → send to backend

## Scene Display
- Image: <img> element with CSS transition: opacity 0.8s ease
- Swap by setting new src, toggling opacity for crossfade
- Audio: <audio> element with autoplay
- Subtitle: narration text displayed below image

## WebSocket Flow (preferred)
```
Client connects to ws://localhost:8000/ws/session
Client sends: { "type": "frame", "data": "base64..." } every 8s
Server sends: { "type": "scene", "assets": SceneAssets } when new scene ready
Server sends: { "type": "emotion", "data": EmotionReading } after each frame analysis
Client sends: { "type": "start", "genre": "mystery" } to begin
Client sends: { "type": "reset" } to restart
```

## Fallback (REST polling if WS is buggy)
- POST /api/emotion every 8s with frame
- GET /api/story/state to check if scene changed
- GET /api/content/current for latest SceneAssets

## States
1. **IDLE**: title screen, genre picker, camera permission prompt
2. **CALIBRATING**: 3-second countdown, captures baseline emotion
3. **PLAYING**: film running, scenes auto-advancing
4. **DECIDING**: brief "Director is thinking..." overlay at decision points
5. **ENDED**: show "Your Film DNA" — list of scenes played, ending reached, emotion chart

## Error states
- Camera denied → show notice, run linear story (no adaptation)
- WebSocket disconnect → fall back to REST polling
- Scene image missing → show dark background with narration text only
EOF
```

---

## PHASE 4: PYDANTIC MODELS

```bash
cat > backend/app/models.py << 'PYEOF'
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class EmotionType(str, Enum):
    ENGAGED = "engaged"
    BORED = "bored"
    CONFUSED = "confused"
    AMUSED = "amused"
    TENSE = "tense"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"


class AttentionType(str, Enum):
    SCREEN = "screen"
    AWAY = "away"
    UNCERTAIN = "uncertain"


class Pacing(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class EmotionReading(BaseModel):
    primary_emotion: EmotionType
    intensity: int = Field(ge=1, le=10)
    attention: AttentionType
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)


class EmotionSummary(BaseModel):
    dominant_emotion: EmotionType
    trend: str  # "rising", "falling", "stable"
    intensity_avg: float
    attention_score: float
    volatility: float
    reading_count: int


class SceneData(BaseModel):
    id: str
    chapter: str = ""
    image_prompt: str = ""
    narration: str = ""
    duration_seconds: int = 16
    next: str | None = None
    is_decision_point: bool = False
    adaptation_rules: dict[str, str] | None = None


class SceneDecision(BaseModel):
    next_scene_id: str
    override_narration: str | None = None
    mood_shift: str | None = None
    pacing: Pacing = Pacing.MEDIUM
    reasoning: str = ""


class SceneAssets(BaseModel):
    scene_id: str
    image_base64: str | None = None
    audio_base64: str | None = None
    narration_text: str
    mood: str
    chapter: str
    duration_seconds: int = 16


class StoryState(BaseModel):
    current_scene_id: str = "opening"
    scenes_played: list[str] = []
    current_chapter: str = "The Arrival"
    genre: str = "mystery"


class FrameInput(BaseModel):
    image_base64: str


class SessionMessage(BaseModel):
    type: str  # "frame", "start", "reset"
    data: str | None = None
    genre: str | None = None
PYEOF
```

---

## PHASE 5: STORY DATA

```bash
cat > story.json << 'STORYEOF'
{
  "title": "The Inheritance",
  "genre": "mystery",
  "scenes": {
    "opening": {
      "id": "opening",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre, moody atmosphere: A lone silhouette stands before a towering Victorian mansion at dusk. Fog rolls across a gravel driveway. A single warm light glows from an upstairs window. Dead ivy climbs the stone walls. 16:9 aspect ratio, dramatic rim lighting, desaturated cool tones.",
      "narration": "The letter arrived three days ago. No return address. No signature. Just an address and two words: Come alone.",
      "duration_seconds": 18,
      "next": "foyer",
      "is_decision_point": false
    },
    "foyer": {
      "id": "foyer",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre: A grand Victorian foyer seen from the entrance. A dusty chandelier hangs crooked. Faded portraits line the walls, their eyes seeming to follow. A wide staircase ascends into shadow. A single set of fresh footprints in the dust leads deeper inside. 16:9, low-key lighting, warm amber from chandelier contrasting cold blue moonlight from windows.",
      "narration": "The front door was unlocked. Inside, the air tasted of dust and old wood, but something else lingered. Perfume. Fresh. As if someone had walked through just moments ago.",
      "duration_seconds": 17,
      "next": "sound_upstairs",
      "is_decision_point": false
    },
    "sound_upstairs": {
      "id": "sound_upstairs",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre: Looking up a dark Victorian staircase from below. At the top, a faint strip of golden light spills from beneath a closed door. Dust particles float in a shaft of moonlight. The bannister casts long dramatic shadows. 16:9, extreme contrast, chiaroscuro lighting.",
      "narration": "A sound from upstairs. Footsteps? Or just the old house settling? The light beneath that door flickered, as if someone had just walked past it.",
      "duration_seconds": 15,
      "next": "decision_1",
      "is_decision_point": false
    },
    "decision_1": {
      "id": "decision_1",
      "is_decision_point": true,
      "adaptation_rules": {
        "engaged": "upstairs_door",
        "tense": "upstairs_door",
        "amused": "upstairs_door",
        "bored": "figure_appears",
        "neutral": "figure_appears",
        "confused": "foyer_detail",
        "surprised": "upstairs_door",
        "default": "upstairs_door"
      }
    },
    "upstairs_door": {
      "id": "upstairs_door",
      "chapter": "The Study",
      "image_prompt": "Cinematic film still, mystery genre: A dark upstairs hallway of a Victorian mansion. Multiple closed doors on each side. One door at the end is slightly ajar, warm amber light spilling out. The wallpaper is peeling. A shadow moves behind the cracked door. 16:9, tension-building composition, shallow depth of field.",
      "narration": "Each stair groaned underfoot. The hallway stretched longer than it should have. At the end, one door stood slightly open, light pouring through the crack like an invitation. Or a trap.",
      "duration_seconds": 16,
      "next": "study_reveal",
      "is_decision_point": false
    },
    "figure_appears": {
      "id": "figure_appears",
      "chapter": "The Stranger",
      "image_prompt": "Cinematic film still, mystery genre, high tension: A dark figure stands at the far end of the Victorian foyer, half-hidden in shadow. Only their silhouette is visible against a moonlit window. They are perfectly still, watching. The protagonist's shadow stretches toward them. 16:9, dramatic backlighting, film noir style.",
      "narration": "A voice, calm and measured, came from behind. 'You're late. We've been waiting.' A figure stepped from the shadows. Their face was still hidden, but their voice carried the weight of someone used to being obeyed.",
      "duration_seconds": 17,
      "next": "hidden_room",
      "is_decision_point": false
    },
    "foyer_detail": {
      "id": "foyer_detail",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre: Close-up of a Victorian foyer table. A half-burned candle, a set of old keys, and an envelope with a broken wax seal. The envelope has the same handwriting as the letter. Dust everywhere except around these objects — they were placed recently. 16:9, macro detail, warm candlelight.",
      "narration": "Wait. On the side table, arranged with deliberate care: a candle still warm to the touch, a ring of iron keys, and another envelope. The same handwriting. This one read: 'You are not the first. You will not be the last.'",
      "duration_seconds": 18,
      "next": "upstairs_door",
      "is_decision_point": false
    },
    "study_reveal": {
      "id": "study_reveal",
      "chapter": "The Study",
      "image_prompt": "Cinematic film still, mystery genre: A cluttered Victorian study. Papers scattered across a mahogany desk. A wall of old photographs connected by red string. A fireplace with dying embers. On the desk, a photograph face-down. The room looks like someone left in a hurry. 16:9, warm firelight mixed with cold window light, detective thriller aesthetic.",
      "narration": "The study was a storm of paper. Notes, photographs, newspaper clippings, all connected by lengths of red string pinned to the wall. Someone had been investigating something. For years. The photograph on the desk was face down. Slowly, you turned it over.",
      "duration_seconds": 18,
      "next": "decision_2",
      "is_decision_point": false
    },
    "hidden_room": {
      "id": "hidden_room",
      "chapter": "The Stranger",
      "image_prompt": "Cinematic film still, mystery genre: A hidden room beneath a Victorian staircase, revealed by a swung-open panel. Inside: a round table with five chairs. Three people sit in shadow, each holding an identical envelope. A single bare bulb hangs overhead. The mood is conspiratorial. 16:9, overhead harsh lighting, intimate and claustrophobic.",
      "narration": "Behind the staircase, a panel swung open. Inside was a room that shouldn't exist. A round table. Three strangers, each clutching the same envelope. They looked up. One of them whispered: 'So there are five of us after all.'",
      "duration_seconds": 18,
      "next": "decision_2",
      "is_decision_point": false
    },
    "decision_2": {
      "id": "decision_2",
      "is_decision_point": true,
      "adaptation_rules": {
        "engaged": "conspiracy_deep",
        "tense": "conspiracy_deep",
        "surprised": "conspiracy_deep",
        "bored": "twist_reveal",
        "neutral": "twist_reveal",
        "amused": "dark_humor_beat",
        "confused": "narrator_explains",
        "default": "conspiracy_deep"
      }
    },
    "conspiracy_deep": {
      "id": "conspiracy_deep",
      "chapter": "The Truth",
      "image_prompt": "Cinematic film still, mystery genre: A wall of photographs and documents with red string connections forming a complex web. In the center, a faded family photograph shows five children standing before this very mansion. One face is circled in red. The protagonist's reflection is visible in the glass frame, and the circled face looks exactly like them. 16:9, revelation moment lighting, dramatic focus pull.",
      "narration": "The red strings converged on a single photograph. Five children, standing before this very mansion, decades ago. And there, in the center, a face you recognized. Because it was yours.",
      "duration_seconds": 17,
      "next": "decision_3",
      "is_decision_point": false
    },
    "twist_reveal": {
      "id": "twist_reveal",
      "chapter": "The Truth",
      "image_prompt": "Cinematic film still, mystery genre, shock reveal: A mirror in a dark Victorian room. The protagonist stares at their reflection, but the reflection is wearing different clothes — older clothes, from decades past. Behind the reflection, the room looks pristine and new, as it was fifty years ago. 16:9, split reality composition, supernatural undertone.",
      "narration": "The mirror in the hallway caught your eye. But the reflection wasn't right. The clothes were wrong. The room behind you looked new, unlived in. And in the mirror, the figure smiled. You did not.",
      "duration_seconds": 18,
      "next": "decision_3",
      "is_decision_point": false
    },
    "dark_humor_beat": {
      "id": "dark_humor_beat",
      "chapter": "The Truth",
      "image_prompt": "Cinematic film still, dark comedy meets mystery: A Victorian dining room set for a formal dinner. Every plate has a different cryptic note on it instead of food. One reads 'You should have stayed home.' A cat sits regally in the host's chair. The chandelier is slightly crooked. 16:9, absurdist composition, Wes Anderson meets Hitchcock.",
      "narration": "The dining room was set for five. Instead of food, each plate held a folded note. Yours read: 'Congratulations. You're the only one who came willingly.' A ginger cat sat in the host's chair, watching with what could only be described as judgment.",
      "duration_seconds": 17,
      "next": "decision_3",
      "is_decision_point": false
    },
    "narrator_explains": {
      "id": "narrator_explains",
      "chapter": "The Truth",
      "image_prompt": "Cinematic film still, mystery genre: An overhead bird's-eye view of the entire Victorian mansion layout, like a dollhouse cross-section. Rooms are visible with tiny figures in them. Red dotted lines show the path the protagonist has taken. It looks like a board game. 16:9, architectural illustration style meets cinema, warm muted tones.",
      "narration": "Let me catch you up. This mansion belonged to the Aldric family. Fifty years ago, the patriarch vanished, leaving his fortune to 'those who prove worthy.' Five letters were sent. You're one of five. Everyone in this house received the same invitation. And one of them already knows the secret.",
      "duration_seconds": 20,
      "next": "decision_3",
      "is_decision_point": false
    },
    "decision_3": {
      "id": "decision_3",
      "is_decision_point": true,
      "adaptation_rules": {
        "engaged": "ending_solve",
        "tense": "ending_bittersweet",
        "surprised": "ending_twist",
        "bored": "ending_twist",
        "neutral": "ending_bittersweet",
        "amused": "ending_solve",
        "confused": "ending_bittersweet",
        "default": "ending_solve"
      }
    },
    "ending_solve": {
      "id": "ending_solve",
      "chapter": "The End",
      "image_prompt": "Cinematic film still, mystery genre, triumphant resolution: Dawn breaks through the Victorian mansion windows. The protagonist stands at the patriarch's desk, holding a golden key. Behind them, the wall of red strings has been reorganized into a clear pattern. The other four strangers stand in the doorway, some looking relieved, some shocked. Golden morning light floods the room. 16:9, warm hopeful lighting, resolution composition.",
      "narration": "By dawn, the pieces had fallen into place. The inheritance was never the fortune. It was the truth. The Aldric patriarch had hidden it here, in plain sight, waiting for someone curious enough to find it. You turned the key. And for the first time that night, you smiled.",
      "duration_seconds": 20,
      "next": null,
      "is_decision_point": false
    },
    "ending_bittersweet": {
      "id": "ending_bittersweet",
      "chapter": "The End",
      "image_prompt": "Cinematic film still, mystery genre, melancholic resolution: The protagonist walks away from the Victorian mansion at dawn, gravel crunching underfoot. They carry a single photograph. Behind them, the mansion looms in morning mist. One window still glows. Their expression is thoughtful, carrying the weight of what they've learned. 16:9, bittersweet morning light, lone figure composition.",
      "narration": "You left at dawn with nothing but a photograph and a truth you wished you didn't know. The inheritance was real, but its price was understanding what the Aldric family had done. Some doors, once opened, can never be closed. Behind you, one window still glowed. Someone was still inside. And they were watching you leave.",
      "duration_seconds": 22,
      "next": null,
      "is_decision_point": false
    },
    "ending_twist": {
      "id": "ending_twist",
      "chapter": "The End",
      "image_prompt": "Cinematic film still, mystery genre, final twist: The protagonist sits in the host's chair at the round table, now alone. Before them lies a new envelope — one they didn't bring. It has someone else's name on it. The camera angle suggests they have become what they set out to investigate. A sixth chair has appeared. 16:9, unsettling symmetry, circular narrative composition, cold blue tones.",
      "narration": "The mansion was empty now. But on the table, a new envelope. Someone else's name. And in the handwriting you now recognized as your own. The door behind you closed. It locked. And somewhere in the walls, a clock began to tick. How long until the next one arrives?",
      "duration_seconds": 22,
      "next": null,
      "is_decision_point": false
    }
  }
}
STORYEOF
```

---

## PHASE 6: SLASH COMMANDS

```bash
# /implement — the main build command
cat > .claude/commands/implement.md << 'EOF'
Implement the module described in the spec file at: docs/specs/$ARGUMENTS

Process:
1. Read the spec file completely
2. Read backend/app/models.py for all Pydantic types
3. Read CLAUDE.md for conventions and constraints
4. Implement in the appropriate file under backend/app/
5. Write matching tests in backend/tests/ — ALL Gemini calls must be mocked
6. Run: cd backend && python -m pytest tests/ -v --tb=short
7. If tests fail, fix and re-run (max 3 retries)
8. Report: what was implemented, what tests pass, any issues
EOF

# /fix — error resolution
cat > .claude/commands/fix.md << 'EOF'
An error has occurred: $ARGUMENTS

Process:
1. Read the full error/traceback
2. Identify the exact file and line
3. Read that file and the relevant spec in docs/specs/
4. Determine root cause (type error, logic error, import error, API error, missing dep)
5. Apply the minimal fix that aligns with the spec
6. Run: cd backend && python -m pytest tests/ -v --tb=short
7. If new failures appear, fix those too (max 3 cycles)
8. Report: what was wrong, what you fixed, test results

Rules:
- Do NOT change models.py unless the spec requires it
- Do NOT add new pip dependencies without flagging it
- Do NOT make real Gemini API calls — use mocks in tests
EOF

# /test — run and analyze tests
cat > .claude/commands/test.md << 'EOF'
Run tests for: $ARGUMENTS (leave empty for all)

Process:
1. If empty: cd backend && python -m pytest tests/ -v --tb=short
2. If module specified: cd backend && python -m pytest tests/test_$ARGUMENTS.py -v --tb=short
3. For any failures:
   - Read the failing test and the implementation
   - Read the spec in docs/specs/
   - Fix the bug (in test or impl, whichever is wrong per spec)
   - Re-run
4. Report: pass/fail summary, any fixes applied
EOF

# /commit — clean incremental commits
cat > .claude/commands/commit.md << 'EOF'
Review all uncommitted changes and make clean git commits.

Process:
1. Run: git diff --stat
2. Group changes by module (emotion, director, pipeline, frontend, story, config)
3. For each group, make a separate commit:
   - git add [relevant files]
   - git commit -m "feat|fix|test|refactor(module): brief description"
4. Never commit: .env, __pycache__, node_modules, .pyc, .venv
5. Run: git log --oneline -5
6. Report what was committed
EOF

# /e2e — end-to-end test (burns real credits)
cat > .claude/commands/e2e.md << 'EOF'
Run an end-to-end integration test with REAL Gemini API calls.
WARNING: This burns API credits (~$0.20 per run). Only run after all unit tests pass.

Process:
1. Verify all unit tests pass first: cd backend && python -m pytest tests/ -v
2. If any fail, STOP and fix them first
3. Start backend: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &
4. Wait 3 seconds for startup
5. Test each endpoint with real data:
   a. POST /api/story/reset
   b. GET /api/story/scene/opening → verify SceneData
   c. POST /api/emotion with a test image → verify EmotionReading
   d. POST /api/director/decide with test data → verify SceneDecision
   e. POST /api/content/generate → verify SceneAssets (this calls real image gen)
6. Kill the server
7. Report: which endpoints work, which fail, cost estimate
EOF

# /wire — connect all modules together
cat > .claude/commands/wire.md << 'EOF'
Wire all implemented modules together in backend/app/main.py.

Process:
1. Read ALL implementations: emotion_service.py, director_agent.py, content_pipeline.py, story_engine.py
2. Read CLAUDE.md for endpoint definitions
3. Create the FastAPI app in main.py with:
   - CORS middleware (allow all origins for hackathon)
   - Static file serving for frontend/
   - All REST endpoints from CLAUDE.md
   - WebSocket endpoint /ws/session that orchestrates the full loop
   - Startup event that loads story.json
4. The WebSocket handler should:
   - Accept connection
   - On "start" message: reset story state, send opening scene
   - On "frame" message: analyze emotion, check if decision needed, if so run director + content pipeline, send new scene
   - On "reset": reset state
5. Run: cd backend && python -m pytest tests/ -v (ensure nothing broke)
6. Start server and verify endpoints respond
EOF

# /frontend — build the frontend
cat > .claude/commands/frontend.md << 'EOF'
Build the frontend as a single index.html file.

Process:
1. Read docs/specs/m4_frontend.md completely
2. Read CLAUDE.md for the layout spec
3. Create frontend/index.html with inline CSS and JS (no build step, no npm)
4. Implement:
   - Webcam capture with getUserMedia
   - Scene image display with CSS crossfade transitions
   - Audio playback element
   - Emotion indicator (emoji + label + intensity bar)
   - Story metadata display (chapter, scene count, mood)
   - WebSocket connection to ws://localhost:8000/ws/session
   - Start/Reset buttons
   - Genre selector (pre-filled with "mystery")
   - Calibration countdown (3 seconds)
   - End screen showing scenes played and which ending
5. Style it dark and cinematic — dark background, minimal UI, let the scene image dominate
6. Test by opening in browser with backend running
EOF
```

---

## PHASE 7: SUBAGENTS

```bash
# Error fixer subagent
cat > .claude/subagents/error-fixer.md << 'EOF'
---
description: "Diagnoses and fixes errors by tracing through logs, source, and specs. Use when tests fail or runtime errors occur."
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

You are the Error Fixer for Director's Cut.

Process:
1. TRACE: Read the full error. Find the exact file:line.
2. CONTEXT: Read that file. Read the spec in docs/specs/. Read models.py.
3. ROOT CAUSE: Is it a type error, logic error, import, API, or config issue?
4. FIX: Minimal change that aligns with the spec. Do not refactor unrelated code.
5. VERIFY: Run `cd backend && python -m pytest tests/ -v --tb=short`
6. REPORT: One paragraph — what broke, why, what you fixed.

Hard rules:
- Max 3 fix attempts. After 3, stop and report what's still broken.
- Never change models.py unless spec requires it.
- Never add pip dependencies.
- Never make real Gemini API calls.
- If it's a Gemini rate limit or credit issue, report it — do not retry.
EOF

# Test writer subagent
cat > .claude/subagents/test-writer.md << 'EOF'
---
description: "Writes pytest unit tests for modules. All Gemini calls must be mocked. Triggered when new modules need test coverage."
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

You are the Test Writer for Director's Cut.

When writing tests for a module:
1. Read the spec in docs/specs/ for expected behavior
2. Read models.py for type definitions
3. Read the implementation to understand internals
4. Write tests in backend/tests/test_{module}.py

Test requirements:
- Use pytest + pytest-asyncio for async functions
- Mock ALL Gemini API calls with unittest.mock.patch or monkeypatch
- Create mock responses that match expected Gemini output format
- Cover: happy path, error handling (API fails → fallback), edge cases, type validation
- Each test is independent — no shared mutable state
- Descriptive names: test_emotion_returns_neutral_on_api_failure

5. Run tests and fix any issues
6. Report: number of tests, all passing, coverage summary
EOF

# Committer subagent
cat > .claude/subagents/committer.md << 'EOF'
---
description: "Makes clean incremental git commits grouped by module. Triggered after implementation work."
allowed-tools: Read, Bash(git *), Grep, Glob
---

You are the Committer for Director's Cut.

Process:
1. Run git status and git diff --stat
2. Group changes by module (emotion, director, pipeline, frontend, story, wire, test, config)
3. For each group:
   - Stage only those files: git add [files]
   - Commit: git commit -m "feat|fix|test(module): description"
4. Never commit: .env, __pycache__, .venv, node_modules, *.pyc
5. If changes look incomplete/broken, flag them — do NOT commit
6. Report: git log --oneline -5
EOF
```

---

## PHASE 8: CONFTEST (shared test fixtures)

```bash
cat > backend/tests/conftest.py << 'CONFEOF'
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def sample_emotion_json():
    return {
        "primary_emotion": "engaged",
        "intensity": 7,
        "attention": "screen",
        "confidence": 0.85,
    }


@pytest.fixture
def sample_emotion_json_tense():
    return {
        "primary_emotion": "tense",
        "intensity": 8,
        "attention": "screen",
        "confidence": 0.9,
    }


@pytest.fixture
def sample_emotion_json_bored():
    return {
        "primary_emotion": "bored",
        "intensity": 3,
        "attention": "away",
        "confidence": 0.7,
    }


@pytest.fixture
def mock_gemini_emotion_response(sample_emotion_json):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(sample_emotion_json)
    return mock_resp


@pytest.fixture
def mock_gemini_director_response():
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "next_scene_id": "upstairs_door",
        "mood_shift": "tense",
        "pacing": "medium",
        "reasoning": "Viewer is engaged, deepening the mystery.",
    })
    return mock_resp


@pytest.fixture
def story_data():
    story_path = Path(__file__).parent.parent.parent / "story.json"
    with open(story_path) as f:
        return json.load(f)


@pytest.fixture
def fake_frame_base64():
    # 1x1 white pixel JPEG as base64 (valid but tiny image)
    return "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAFBABAAAAAAAAAAAAAAAAAAAACf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKgA/9k="
CONFEOF
```

---

## PHASE 9: INITIAL COMMIT AND LAUNCH

```bash
# Commit everything
git add -A
git commit -m "feat(scaffold): complete project structure, specs, models, story, claude config"

# Verify
git log --oneline
# Should show: feat(scaffold): complete project structure, specs, models, story, claude config

# Launch Claude Code
claude
```

---

## PHASE 10: YOUR FIRST COMMANDS IN CLAUDE CODE

Once Claude Code is running, paste these commands in order:

```
# 1. Orient Claude
> Read CLAUDE.md, then read every file in docs/specs/, then read backend/app/models.py, then read story.json. Confirm you understand the project.

# 2. Build M0 + M1
> /implement m0_story.md
> /implement m1_emotion.md
> /commit

# 3. Build M3
> /implement m3_pipeline.md
> /commit

# 4. Build M2
> /implement m2_director.md
> /commit

# 5. Wire it all
> /wire
> /commit

# 6. Frontend
> /frontend
> /commit

# 7. End-to-end test
> /e2e

# 8. Polish and submit
> /commit
```

---

## ⏱️ TIME BUDGET

| Block | Duration | What |
|---|---|---|
| Setup + orient | 15 min | Env, deps, Claude reads everything |
| M0 + M1 | 45 min | Story engine + emotion service + tests |
| M3 | 45 min | Content pipeline (image + TTS) + tests |
| M2 | 45 min | Director agent + tests |
| Wire | 30 min | main.py, all endpoints, WebSocket |
| Frontend | 45 min | index.html, webcam, scene display |
| E2E + fix | 30 min | Real API calls, debug integration |
| Polish + submit | 45 min | README, demo video, git push, submit |
| **Total** | **~5.5 hrs** | 30 min buffer |
