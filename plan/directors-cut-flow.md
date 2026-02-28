# Director's Cut — Full UX Flow & Emotion-Adaptation Architecture

---

## WHAT THE USER SEES (Screen Layout)

```
┌─────────────────────────────────────────────────────────┐
│                    DIRECTOR'S CUT                        │
│              "A film that watches you back"               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   ┌─────────────────────────────────┐  ┌──────────────┐ │
│   │                                 │  │  YOUR CAMERA  │ │
│   │                                 │  │  ┌──────────┐ │ │
│   │      SCENE IMAGE                │  │  │  👤 face  │ │ │
│   │   (Nano Banana Pro generated)   │  │  └──────────┘ │ │
│   │                                 │  │               │ │
│   │                                 │  │ Detected:     │ │
│   │                                 │  │ 😊 Engaged    │ │
│   │                                 │  │ Intensity: 8  │ │
│   └─────────────────────────────────┘  └──────────────┘ │
│                                                          │
│   ┌─────────────────────────────────────────────────────┐│
│   │ 🔊 "The door creaked open, revealing a room that    ││
│   │ hadn't been touched in decades..."                   ││
│   │                          — Narrator (Gemini TTS)     ││
│   └─────────────────────────────────────────────────────┘│
│                                                          │
│   ┌──────────────────────────┐  ┌───────────────────────┐│
│   │ 📖 Chapter: The Arrival  │  │ 🎭 Mood: Mysterious   ││
│   │ Scene: 3 of ~12          │  │ Pacing: Slow build    ││
│   │ Path: Curious Explorer   │  │ Tone shift: ↗ darker  ││
│   └──────────────────────────┘  └───────────────────────┘│
│                                                          │
│   [ ▶ Start Experience ]  [ 🎬 Pick Genre ]  [ ⟳ Reset ]│
└─────────────────────────────────────────────────────────┘
```

**Key principle:** The main scene image dominates. The webcam feed is small (top-right corner) so the viewer isn't self-conscious but can see the system is watching. The emotion indicator is subtle — judges will notice it and that becomes part of the "wow."

---

## STEP-BY-STEP USER JOURNEY

### Phase 1: Setup (15 seconds)
1. User lands on the app → sees a cinematic title screen with genre selection
2. Browser requests webcam permission → small preview appears top-right
3. User picks a genre (or gets a default): **Mystery**, **Sci-Fi**, **Romance**, **Thriller**
4. System does a quick "calibration" frame — captures resting face as emotional baseline

### Phase 2: The Film Begins (2-3 minutes)
5. Opening scene image generates + narration begins playing
6. Every ~8-10 seconds, a new webcam frame is silently analyzed for emotion
7. The story progresses through scenes — each scene is:
   - A generated image (Nano Banana Pro)
   - Narrated text (Gemini TTS)
   - ~15-20 seconds of "screen time" per scene
8. At **decision points** (every 3-4 scenes), the Director Agent evaluates accumulated emotion data and chooses the next narrative branch

### Phase 3: Adaptation Moments (the "wow")
9. The viewer's face visibly influences the story:
   - Viewer smiles → story leans warmer, introduces a likeable character
   - Viewer looks confused → narrator adds clarifying context, pacing slows
   - Viewer looks bored/neutral → PLOT TWIST or dramatic reveal
   - Viewer looks tense/scared → tension either escalates (thriller) or releases (comedy beat)
10. The emotion indicator on screen briefly highlights when a decision was influenced by the viewer's state

### Phase 4: Conclusion (~30 seconds)
11. Story reaches one of 3-4 possible endings based on the path taken
12. End screen shows a "Your Film DNA" summary: the emotional journey mapped over time, key decision points, which ending you got

---

## THE EMOTION-ADAPTATION ENGINE (Technical Detail)

### Layer 1: Emotion Capture

**What:** Capture a webcam frame every 8-10 seconds, send to Gemini 3 Pro with a structured output prompt.

**Why not real-time?** Reduces API calls, avoids rate limits, and facial expressions don't change meaningfully faster than this. Also keeps token costs manageable.

**Prompt to Gemini 3 Pro (vision):**
```
Analyze this webcam image of a person watching a film. Return ONLY a JSON object:
{
  "primary_emotion": "engaged|bored|confused|amused|tense|surprised|neutral",
  "intensity": 1-10,
  "attention_direction": "screen|away|phone",
  "micro_expressions": ["smiling", "furrowed_brow", "wide_eyes", "jaw_drop", "squinting"],
  "confidence": 0.0-1.0
}
Do not include any other text.
```

**Settings:**
- Use `media_resolution_low` (280 tokens) — we only need face-level detail, not fine text
- Use `thinking_level: "none"` — fast response, no deep reasoning needed for this step
- Use Gemini 3 Flash (cheaper, faster) for emotion detection, save Pro for the Director

**Output example:**
```json
{
  "primary_emotion": "tense",
  "intensity": 7,
  "attention_direction": "screen",
  "micro_expressions": ["furrowed_brow", "squinting"],
  "confidence": 0.85
}
```

### Layer 2: Emotion Accumulator (Application State)

The raw per-frame emotions are noisy. We smooth them into a rolling window:

```python
class EmotionState:
    history: list[EmotionReading]  # last 6-8 readings (~1 min of viewing)
    
    @property
    def dominant_emotion(self) -> str:
        """Most frequent emotion in window"""
    
    @property
    def trend(self) -> str:
        """Is engagement rising, falling, or stable?"""
    
    @property
    def intensity_avg(self) -> float:
        """Average intensity over window"""
    
    @property
    def attention_score(self) -> float:
        """% of recent frames where viewer was looking at screen"""
    
    def trigger_adaptation(self) -> bool:
        """Returns True if we have enough signal to make a story decision"""
        # True if: 3+ consistent readings of same emotion, 
        # OR sudden spike in intensity, OR attention drop
```

**Key insight:** We don't react to every single frame. We wait for a *pattern* — 3+ consistent readings showing boredom, or a sudden spike showing surprise. This prevents jittery, random story changes.

### Layer 3: The Director Agent (The Brain)

This is the core intelligence. It's a Gemini 3 Pro agent (via LlamaIndex Workflow) that takes in:
- Current story state (which scene, which branch, what's happened so far)
- Emotion accumulator summary
- Genre constraints
- Available narrative branches

**And outputs:**
- The next scene to show
- Any adjustments to pacing, tone, or content
- Which content generation tools to call

```python
DIRECTOR_SYSTEM_PROMPT = """
You are the Director of an interactive film. You control the narrative based 
on the viewer's emotional state.

CURRENT STORY STATE:
- Genre: {genre}
- Current chapter: {chapter}
- Scene number: {scene_num}
- Story so far: {story_summary}
- Available branches: {branches}

VIEWER EMOTIONAL STATE:
- Dominant emotion: {dominant_emotion}
- Trend: {trend} (rising/falling/stable)
- Intensity: {intensity}/10
- Attention: {attention_score}%
- Recent pattern: {emotion_pattern}

ADAPTATION RULES:
1. BORED/NEUTRAL + low intensity → Inject a plot twist, revelation, or 
   dramatic event. Increase pacing. Shorten scene duration.
2. ENGAGED/AMUSED + high intensity → Continue current direction. This is 
   working. Deepen the emotional thread.
3. TENSE + high intensity → You have two options based on genre:
   - Thriller/Mystery: Escalate slightly, then provide a small relief beat
   - Romance/Sci-fi: Provide resolution or a tender moment
4. CONFUSED + any intensity → Slow down. Have the narrator provide context. 
   Simplify the next scene. Don't introduce new characters.
5. SURPRISED + spike → Great! The last scene worked. Let the moment breathe. 
   Don't immediately follow with another surprise.
6. ATTENTION DROP → The viewer looked away. Next scene needs a strong visual 
   or audio hook to pull them back.

OUTPUT FORMAT (JSON):
{
  "next_scene_id": "chapter2_scene3b",
  "scene_description": "A detailed visual description for image generation",
  "narration_text": "The narrator's script for this scene",
  "mood": "tense|warm|mysterious|exciting|melancholic|hopeful",
  "pacing": "slow|medium|fast",
  "reasoning": "Brief explanation of why this choice was made"
}
"""
```

### Layer 4: Content Generation Pipeline (Parallel)

Once the Director decides the next scene, three things happen IN PARALLEL:

```
Director Output
     │
     ├──→ [Nano Banana Pro] Generate scene image from scene_description
     │         prompt: "Cinematic film still, {genre} genre, {mood} mood: 
     │                  {scene_description}. 16:9 aspect ratio, 
     │                  dramatic lighting, movie quality."
     │
     ├──→ [Gemini TTS] Generate narration audio from narration_text
     │         voice: matched to genre (deep for thriller, warm for romance)
     │
     └──→ [Gemini 3 Pro] Pre-generate the NEXT 2 possible branches
               (so they're ready when the next decision point hits)
```

**The pre-generation trick is critical.** While the current scene plays for 15-20 seconds, we're already generating the next 2 possible scenes. When the Director makes the decision, the content is already cached and displays instantly.

### Layer 5: Scene Presentation

```
Timeline of a single scene (~15-20 seconds):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
│ Fade in image │ Narration plays │ Emotion capture │ Fade transition │
│   (1 sec)     │  (8-12 sec)     │ (frame grabbed) │   (1-2 sec)     │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                        │
                                        ▼
                              Emotion sent to accumulator
                              If decision point → Director Agent fires
                              Next scene loads (from pre-generated cache)
```

---

## THE STORY STRUCTURE

Don't try to generate a fully freeform story. Use a **branching tree** with pre-defined structures:

```
Opening Scene (fixed)
    │
    ▼
Chapter 1: Setup (2-3 scenes, linear)
    │
    ▼
Decision Point 1 ──→ Branch A (viewer engaged) vs Branch B (viewer bored/neutral)
    │                      │
    ▼                      ▼
Chapter 2A: Deepen     Chapter 2B: Twist
(2-3 scenes)           (2-3 scenes, higher energy)
    │                      │
    ▼                      ▼
Decision Point 2 ──→ Based on emotion at this point
    │
    ▼
Chapter 3: Climax (2-3 scenes, converges)
    │
    ▼
Decision Point 3 ──→ Final branch
    │
    ├──→ Ending A: Triumphant / Happy
    ├──→ Ending B: Bittersweet / Thoughtful  
    └──→ Ending C: Dark / Twist ending
```

**Total scenes:** ~12-15 (but only ~8-10 play in any given viewing)
**Total runtime:** ~2.5-3 minutes (perfect for demo)

### Pre-Written Story Skeleton (Mystery Genre Example)

```
OPENING: A stranger arrives at an old mansion on a stormy night.
         A letter in their pocket reads: "Come alone. Trust no one."

CH1-S1: They approach the front door. It's already open.
CH1-S2: Inside, a grand foyer. Dusty portraits line the walls.
CH1-S3: A sound from upstairs — footsteps? Or the wind?

DECISION 1:
  → Viewer engaged/tense → They go upstairs (lean into mystery)
  → Viewer bored/neutral → A figure appears behind them (jump scare energy)

CH2A-S1: Upstairs hallway, doors on each side. One has light under it.
CH2A-S2: They open the door. A study with papers scattered everywhere.
CH2A-S3: Among the papers — a photograph. It's THEM, decades younger.

CH2B-S1: The figure speaks: "You're late. We've been waiting."
CH2B-S2: They're led to a hidden room beneath the staircase.
CH2B-S3: Inside: a group of strangers, all holding the same letter.

DECISION 2:
  → Viewer surprised/engaged → Deepen the conspiracy
  → Viewer confused → Narrator explains, slows down
  → Viewer amused → Add dark humor element

CH3: Climax converges — the truth about the mansion is revealed.

DECISION 3 (ending):
  → High engagement throughout → Ending A: They solve the mystery, escape
  → Mixed emotions → Ending B: They solve it but at a personal cost
  → Low engagement / boredom detected → Ending C: Wild twist — it was all a dream... or was it?
```

---

## COMPLETE DATA FLOW DIAGRAM

```
┌──────────┐     frame every 8s      ┌─────────────────────┐
│  WEBCAM  │ ───────────────────────→ │  GEMINI 3 FLASH     │
│ (browser)│                          │  (emotion detection) │
└──────────┘                          └──────────┬──────────┘
                                                 │ JSON emotion
                                                 ▼
                                      ┌─────────────────────┐
                                      │  EMOTION ACCUMULATOR │
                                      │  (Python state)      │
                                      │  - rolling window    │
                                      │  - trend detection   │
                                      │  - trigger logic     │
                                      └──────────┬──────────┘
                                                 │ when triggered
                                                 ▼
┌──────────────┐   story state +    ┌──────────────────────────┐
│  STORY GRAPH │   emotion summary  │  DIRECTOR AGENT          │
│  (JSON tree) │ ──────────────────→│  (Gemini 3 Pro via       │
│              │                    │   LlamaIndex Workflow)    │
└──────────────┘                    │  + Knowledge base of     │
                                    │    narrative patterns     │
                                    └───────────┬──────────────┘
                                                │ scene decision
                              ┌─────────────────┼───────────────┐
                              ▼                 ▼               ▼
                    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
                    │ NANO BANANA  │  │  GEMINI TTS  │  │ PRE-GEN NEXT │
                    │ PRO          │  │              │  │ 2 BRANCHES   │
                    │ (scene image)│  │ (narration)  │  │ (Gemini Pro) │
                    └──────┬───────┘  └──────┬───────┘  └──────────────┘
                           │                 │
                           ▼                 ▼
                    ┌─────────────────────────────┐
                    │       SCENE RENDERER         │
                    │  (React frontend)            │
                    │  - Display image with fade   │
                    │  - Play narration audio      │
                    │  - Update mood/chapter info   │
                    │  - Show emotion indicator     │
                    └─────────────────────────────┘
```

---

## BUILD ORDER (7 Hours)

| Time | Task | Deliverable |
|---|---|---|
| **Hour 1** (9-10am) | Scaffold: React frontend + Python FastAPI backend. Webcam capture working. Gemini API key verified. | Basic app shell with live webcam preview |
| **Hour 2** (10-11am) | Emotion detection: webcam frame → Gemini Flash → structured JSON emotion. Display on frontend. | Working emotion detector showing live readings |
| **Hour 3** (11am-12pm) | Story engine: Define story graph JSON. Build Director Agent with LlamaIndex Workflow. Wire emotion accumulator → Director. | Director Agent making decisions based on hardcoded test emotions |
| **Hour 4** (12-1pm) | Image generation: Nano Banana Pro integration. Scene image generation from Director's scene_description. Display with fade transitions. | Scenes generating and displaying in sequence |
| **Hour 5** (1-2pm) | Narration: Gemini TTS integration. Audio playback synced with scene display. Wire the full loop end-to-end. | Complete loop: emotion → director → image + audio → display |
| **Hour 6** (2-3pm) | Write the full mystery story skeleton (all branches). Pre-generation pipeline for next branches. Polish transitions. | Full playable story with 3 decision points and 3 endings |
| **Hour 7** (3-4pm) | Demo polish: loading states, error handling, smooth transitions. Test the 3-minute demo flow multiple times. Record 1-min video. | Demo-ready, video submitted |
| **Buffer** (4-5pm) | Bug fixes, submission, catch breath | Submitted by 5pm |

---

## KEY TECHNICAL DECISIONS

**Use Gemini Flash for emotion detection, Pro for the Director.**
Flash is cheaper, faster, and accurate enough for face reading. Save Pro's reasoning power for the creative narrative decisions.

**Pre-generate branches, don't generate on demand.**
The #1 demo killer is waiting 5 seconds for an image to generate while a judge stares at a loading spinner. Pre-generate both possible next scenes while the current one plays.

**Keep the story graph in a simple JSON file, not a database.**
You have 7 hours. A JSON file with the branching structure is perfectly fine. No need for a DB.

**Use `media_resolution_low` for webcam frames.**
280 tokens per frame vs 1120. You're just reading a face, not fine text. This saves tokens and speeds up response time.

**Frontend: React with simple CSS transitions.**
Don't waste time on fancy animations. A 1-second CSS opacity fade between scene images looks cinematic enough. Focus on the content pipeline, not pixel-perfect UI.
