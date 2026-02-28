# Director's Cut — Spec-Driven Development Plan

## 💰 BUDGET REALITY CHECK ($25 Credits)

### Cost Per API Call (February 2026 Pricing)

| API Call | Model | Cost | Notes |
|---|---|---|---|
| Emotion detection (per frame) | Gemini 3 Flash | ~$0.0003 | 280 tokens in (low res image) + ~50 tokens out |
| Director decision | Gemini 3 Pro | ~$0.005 | ~500 tokens in + ~300 tokens out |
| Scene image generation | **Gemini 2.5 Flash Image** | **$0.039** | 1024x1024, 1290 output tokens |
| Scene image generation | **Imagen 4 Fast** | **$0.02** | 1024x1024, cheapest option |
| Narration (TTS) | Gemini 2.5 Flash TTS | ~$0.002 | ~100 tokens of text → audio |
| Pre-gen branch (text only) | Gemini 3 Flash | ~$0.001 | Scene description + narration text |

### Budget for a Full Demo Run (~12 scenes played, ~20 pre-generated)

| Item | Count | Unit Cost | Total |
|---|---|---|---|
| Emotion frames | 25 | $0.0003 | $0.008 |
| Director decisions | 4 | $0.005 | $0.02 |
| Scene images (displayed) | 12 | $0.039 | $0.47 |
| Scene images (pre-gen, unused) | 8 | $0.039 | $0.31 |
| TTS narration | 12 | $0.002 | $0.024 |
| Pre-gen branch text | 8 | $0.001 | $0.008 |
| **Total per run** | | | **~$0.84** |

### Budget Allocation

| Use | Allocation | Runs |
|---|---|---|
| Development & testing | $15 | ~18 full test runs |
| Live demos (judging) | $5 | ~6 full demo runs |
| Buffer / mistakes | $5 | safety net |
| **Total** | **$25** | |

**Key decision: Use Gemini 2.5 Flash Image (Nano Banana) at $0.039/image, NOT Nano Banana Pro at $0.134/image.** This saves ~70% on the biggest cost item. Quality is slightly lower but absolutely fine for a hackathon demo. If Imagen 4 Fast is available in your GCP project, even better at $0.02/image.

**Cost-saving tactics:**
- Use `media_resolution_low` for ALL webcam frames (280 vs 1120 tokens)
- Use Gemini 3 Flash (not Pro) for emotion detection — it's 4x cheaper
- Only use Gemini 3 Pro for the Director Agent decisions (3-4 per run)
- Pre-generate scene TEXT first (cheap), only generate IMAGE when actually needed
- Cache generated images — if the same branch is hit again, reuse the image

---

## 🏗️ SPEC-DRIVEN DEVELOPMENT APPROACH

Instead of vibe coding, we define clear specs for each module, then use Gemini Dev / Claude Code / skills.sh to implement each one against its spec.

### System Architecture (4 Modules)

```
┌─────────────────────────────────────────────────────┐
│                    MODULE MAP                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  M1: EMOTION SERVICE        M2: DIRECTOR AGENT       │
│  ┌──────────────────┐      ┌──────────────────┐     │
│  │ Input: JPEG frame │      │ Input: EmotionState│    │
│  │ Output: EmotionJSON│     │        + StoryState│    │
│  │ Model: Flash       │     │ Output: SceneDecision│  │
│  │ Stateless          │     │ Model: Pro          │   │
│  └──────────────────┘      │ Uses: LlamaIndex    │   │
│                             └──────────────────┘     │
│                                                      │
│  M3: CONTENT PIPELINE       M4: FRONTEND             │
│  ┌──────────────────┐      ┌──────────────────┐     │
│  │ Input: SceneDecision│    │ Input: Scene assets│    │
│  │ Output: image_url   │    │ Output: Rendered UI│    │
│  │         audio_url   │    │ Tech: React/HTML   │    │
│  │ Models: Flash Image │    │ Webcam capture     │    │
│  │         Flash TTS   │    │ Audio playback     │    │
│  └──────────────────┘      └──────────────────┘     │
│                                                      │
│  M0: STORY DATA (JSON)                               │
│  ┌──────────────────────────────────────────────┐   │
│  │ Static story graph with branches, scenes,     │   │
│  │ prompts, and adaptation rules                 │   │
│  └──────────────────────────────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 📋 MODULE SPECS

### M0: Story Data (`story.json`)

**Write this TONIGHT. No code needed. Just JSON.**

```json
{
  "title": "The Inheritance",
  "genre": "mystery",
  "default_mood": "mysterious",
  "scenes": {
    "opening": {
      "id": "opening",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre, moody atmosphere: A lone figure stands before an imposing Victorian mansion at dusk, fog rolling across the gravel driveway, warm light from a single upstairs window. 16:9 aspect ratio, dramatic lighting.",
      "narration": "The letter arrived three days ago. No return address. Just an address, and two words: Come alone.",
      "duration_seconds": 18,
      "next": "hallway",
      "is_decision_point": false
    },
    "hallway": {
      "id": "hallway",
      "chapter": "The Arrival",
      "image_prompt": "Cinematic film still, mystery genre: A grand dusty hallway of a Victorian mansion, portraits lining the walls with eyes that seem to follow, a single chandelier casting long shadows, a staircase ascending into darkness. 16:9.",
      "narration": "The front door was unlocked. Inside, the air was thick with dust and something else — the faint scent of perfume, fresh, as if someone had just walked through.",
      "duration_seconds": 16,
      "next": "decision_1",
      "is_decision_point": false
    },
    "decision_1": {
      "id": "decision_1",
      "is_decision_point": true,
      "adaptation_rules": {
        "engaged_or_tense": "upstairs_light",
        "bored_or_neutral": "figure_appears",
        "amused": "upstairs_light",
        "confused": "hallway_detail",
        "default": "upstairs_light"
      }
    }
    // ... continue for all scenes and branches
  }
}
```

**Target: 15-18 total scenes across all branches, 3 decision points, 3 endings.**

---

### M1: Emotion Service

**Spec:**
```yaml
name: emotion_service
type: stateless function
input: 
  - frame: base64 JPEG from webcam (640x480)
output:
  EmotionReading:
    primary_emotion: enum[engaged, bored, confused, amused, tense, surprised, neutral]
    intensity: int (1-10)
    attention: enum[screen, away, uncertain]
    confidence: float (0-1)
    timestamp: ISO datetime
model: gemini-3-flash (via google-genai SDK)
settings:
  media_resolution: low  # 280 tokens
  thinking_level: none   # no reasoning overhead
  temperature: 0.3       # deterministic
  response_format: JSON
latency_target: <1 second
error_handling: return {primary_emotion: "neutral", confidence: 0} on any failure
```

**Emotion Accumulator (in-memory, runs on backend):**
```yaml
name: emotion_accumulator
type: stateful class
state:
  history: list[EmotionReading]  # rolling window of last 8 readings
  baseline: EmotionReading       # calibration from first frame
methods:
  add_reading(reading) -> void   # append, trim to window
  get_summary() -> EmotionSummary:
    dominant_emotion: str        # mode of last 8
    trend: enum[rising, falling, stable]  # intensity direction
    attention_avg: float         # % of frames with attention=screen
    volatility: float            # std dev of intensities
  should_trigger() -> bool:
    # True if 3+ consistent same-emotion OR intensity spike >4 points
```

---

### M2: Director Agent

**Spec:**
```yaml
name: director_agent
type: LlamaIndex AgentWorkflow
model: gemini-3-pro-preview (via llama-index-llms-google-genai)
input:
  - emotion_summary: EmotionSummary
  - story_state: StoryState
    current_scene_id: str
    scenes_played: list[str]
    story_graph: dict  # from story.json
output:
  SceneDecision:
    next_scene_id: str
    override_narration: str | null  # if Director wants to tweak narration
    mood_shift: str | null          # override scene mood
    pacing: enum[slow, medium, fast]
    reasoning: str                  # for debug display
tools:
  - get_scene_data(scene_id) -> scene object from story.json
  - get_available_branches(decision_id) -> list of branch options
  - get_narrative_pattern(mood, genre) -> retrieval from knowledge base
knowledge_base:
  - LlamaIndex VectorStoreIndex over narrative_patterns.json
  - Contains: genre tropes, pacing rules, emotional arc theory
  - Used via agentic retrieval when Director needs inspiration
settings:
  thinking_level: medium
  temperature: 0.8  # creative but consistent
  thought_signatures: enabled  # maintain reasoning continuity
```

---

### M3: Content Pipeline

**Spec:**
```yaml
name: content_pipeline
type: async parallel pipeline
input: SceneDecision + scene data from story.json
outputs:
  - image_url: str  # generated scene image, served as base64 or temp URL
  - audio_data: bytes  # TTS narration audio

image_generation:
  model: gemini-2.5-flash-image  # $0.039/image, NOT Nano Banana Pro
  prompt_template: |
    {scene.image_prompt}
    Style: cinematic, {story.genre}, {scene_decision.mood_shift or scene.default_mood}
    Aspect ratio: 16:9
    Quality: high detail, dramatic lighting
  settings:
    aspect_ratio: "16:9"
    output_resolution: 1024  # sufficient for demo
  caching: store generated images by scene_id + mood hash
           if cache hit, skip generation (saves $0.039)

tts_generation:
  model: gemini-2.5-flash-preview-tts
  input: scene.narration (or decision.override_narration)
  voice: genre-appropriate (deep male for mystery, warm for romance)
  settings:
    speaking_rate: 0.9  # slightly slower = more dramatic

pre_generation:
  # While current scene plays, pre-gen the NEXT possible scenes
  strategy: |
    1. Look at current scene's "next" field
    2. If next is a decision point, get ALL branches from adaptation_rules
    3. For each branch target: generate image + TTS in parallel
    4. Store in cache
    5. When Director decides, pull from cache → instant display
  max_parallel_pregens: 2  # don't exceed, saves budget
```

---

### M4: Frontend

**Spec:**
```yaml
name: frontend
type: Single Page Application
tech: React + Vite (or plain HTML/JS if faster for you)
layout:
  main_area (70%): Scene image display with CSS fade transitions
  sidebar (30%): 
    top: Webcam preview (small, 200x150px)
    middle: Emotion indicator (emoji + label + intensity bar)
    bottom: Story metadata (chapter, scene#, mood, path)
  bottom_bar: Narration text (subtitle style), playback controls

webcam_capture:
  api: navigator.mediaDevices.getUserMedia
  interval: every 8 seconds
  format: capture frame to canvas → toBlob('image/jpeg', 0.7) → base64
  send: POST to /api/emotion with base64 payload

scene_display:
  transition: CSS opacity fade (0.8s ease-in-out)
  audio: HTML5 Audio element, auto-play when scene loads
  subtitle: Display narration text synced with audio (or just show full text)
  timing: 
    - Scene duration from story.json (15-20s)
    - When duration elapsed → check if next is decision point
    - If decision → wait for Director response → load next scene
    - If linear → load pre-cached next scene immediately

initial_flow:
  1. Title screen with genre selector
  2. "Allow camera" prompt
  3. Calibration frame (3 second countdown)
  4. Film begins
  5. End screen with emotional journey summary

error_states:
  - Camera denied → still works, just no adaptation (linear path)
  - API timeout → use default/fallback branch
  - Image gen fails → show placeholder with narration still playing
```

---

## 🛠️ SKILLS.SH & DEV AUTOMATION STRATEGY

### Development Agents Setup (Do This First Thing Tomorrow)

```bash
# 1. Install skills.sh
npx skills add google-labs-code/stitch-skills  # Google's official dev skills
npx skills add giuseppe-trisciuoglio/developer-kit  # general dev patterns

# 2. Set up your coding agent (Claude Code, Cursor, or Gemini Code Assist)
# Feed it this entire spec document as context

# 3. For each module, the workflow is:
#    a. Give the agent the MODULE SPEC above
#    b. Agent generates implementation
#    c. You review, test against spec, iterate
#    d. Move to next module
```

### Spec-Driven Workflow Per Module

```
FOR EACH MODULE:
  1. SPEC    → Already defined above (input/output/behavior)
  2. TYPES   → Agent generates Pydantic models from spec
  3. IMPL    → Agent implements against types + spec
  4. TEST    → Quick manual test with hardcoded input
  5. WIRE    → Connect to previous module
  6. VERIFY  → End-to-end check
```

### Recommended Dev Order with Time Blocks

```
HOUR 1 (9-10am): PROJECT BOOTSTRAP
  ├── Scaffold: monorepo with /backend (Python) + /frontend (React or HTML)
  ├── Install deps: google-genai, llama-index, llama-index-llms-google-genai, fastapi, uvicorn
  ├── Verify: Gemini API key works (one test call to Flash)
  ├── Load: story.json (written tonight)
  └── Deliverable: "Hello world" — one Gemini call returns a response

HOUR 2 (10-11am): M1 — EMOTION SERVICE
  ├── Implement: emotion endpoint (POST /api/emotion)
  ├── Implement: EmotionAccumulator class
  ├── Test: point webcam at your face, see JSON come back
  └── Deliverable: Working emotion detection with live webcam

HOUR 3 (11-12pm): M3 — CONTENT PIPELINE (image + TTS)
  ├── Implement: image generation with Gemini 2.5 Flash Image
  ├── Implement: TTS generation
  ├── Implement: caching layer (dict keyed by scene_id)
  ├── Test: generate 2-3 test scenes from story.json
  └── Deliverable: Can generate scene image + narration on demand

HOUR 4 (12-1pm): M4 — FRONTEND (basic scene viewer)
  ├── Implement: webcam capture + preview
  ├── Implement: scene display with image + audio + fade transitions
  ├── Implement: emotion indicator display
  ├── Wire: webcam → M1 emotion endpoint → display
  ├── Test: scenes cycle with transitions, emotion shows on screen
  └── Deliverable: Visual app that captures emotion and displays scenes

HOUR 5 (1-2pm): M2 — DIRECTOR AGENT
  ├── Implement: LlamaIndex Workflow with Gemini Pro
  ├── Implement: story graph navigation logic
  ├── Implement: adaptation rules from decision points
  ├── Wire: emotion accumulator → Director → content pipeline → frontend
  ├── Optional: knowledge base for narrative patterns (skip if behind)
  └── Deliverable: Full adaptation loop working end-to-end

HOUR 6 (2-3pm): END-TO-END INTEGRATION + STORY POLISH
  ├── Run full demo 2-3 times
  ├── Fix timing issues (scene too short/long)
  ├── Fix transition glitches
  ├── Tune emotion thresholds (is it triggering too often? not enough?)
  ├── Add the "Your Film DNA" end screen (emotional journey chart)
  └── Deliverable: Smooth 3-minute demo experience

HOUR 7 (3-4pm): DEMO PREP
  ├── Run demo 2-3 more times, iron out any remaining issues
  ├── Record 1-minute demo video (screen + webcam)
  ├── Push to GitHub (public repo)
  ├── Write README.md (what it is, how to run, tech stack, architecture)
  ├── Submit to hackathon portal
  └── Deliverable: SUBMITTED

BUFFER (4-5pm): 
  ├── Fix any last-second issues
  ├── Prepare your 3-minute pitch talking points
  └── Breathe
```

---

## 🎤 PITCH TALKING POINTS (3 minutes)

**0:00-0:30 — Hook:**
"What if a movie could watch you back? What if it knew when you were bored, and threw a plot twist? What if it could tell you were on the edge of your seat, and pushed you further?"

**0:30-1:00 — Demo start:**
"Let me show you. I'm going to sit in front of my camera, and Director's Cut will create a personalized mystery film for me right now."
[Film begins playing]

**1:00-2:00 — Live adaptation:**
[Point out the emotion indicator as it reads your face]
"Notice how it detected I was engaged there — so it's deepening the mystery. Now watch what happens if I look disinterested..."
[Deliberately look bored → story adapts]
"There — it just threw a plot twist because it read my boredom."

**2:00-2:30 — Architecture:**
"Under the hood: Gemini Flash reads my face every 8 seconds. A Director Agent built with LlamaIndex and Gemini Pro decides the narrative. Gemini Flash Image generates every scene. Gemini TTS narrates. All in real-time."

**2:30-3:00 — Vision:**
"Imagine this for Netflix — every viewer gets a different film. For theaters — audience-reactive experiences. For education — content that re-engages when students zone out. The future of storytelling is adaptive."
