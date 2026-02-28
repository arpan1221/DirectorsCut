# Director's Cut — Multi-Agent Dev Orchestration

## The Setup: Three Surfaces, Distinct Roles

```
┌──────────────────────────────────────────────────────────────────┐
│                    YOUR WORKSTATION LAYOUT                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐  ┌────────────────────────────────────┐ │
│  │  CLAUDE CODE         │  │  CURSOR IDE                        │ │
│  │  (Terminal - tmux)   │  │                                    │ │
│  │                      │  │  - Browse / edit files              │ │
│  │  LEAD ORCHESTRATOR   │  │  - Cursor's inline AI for quick    │ │
│  │  + Agent Team panes  │  │    edits, autocomplete, diffs      │ │
│  │                      │  │  - Visual git diff review           │ │
│  │  This is your        │  │  - Run the app (terminal in IDE)   │ │
│  │  command center.     │  │  - Manual testing / browser         │ │
│  │  You talk to the     │  │                                    │ │
│  │  Lead here.          │  │  This is your EYES on the code.    │ │
│  └─────────────────────┘  └────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  BROWSER (localhost:3000 + localhost:8000/docs)               │ │
│  │  - Live app preview                                           │ │
│  │  - FastAPI Swagger docs                                       │ │
│  │  - Gemini API Studio (for manual prompt testing)              │ │
│  └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**Rule of thumb:** Claude Code does the heavy lifting (writing, testing, fixing). Cursor is for reviewing diffs, quick inline edits, and running the app. You are the architect — you issue commands and verify results.

---

## STEP 0: TONIGHT — Repo Bootstrap & Configuration

### 0.1 Create the repo and folder structure

```bash
mkdir directors-cut && cd directors-cut
git init
mkdir -p backend/app backend/tests frontend/src
mkdir -p .claude/commands .claude/skills .claude/subagents
touch backend/app/__init__.py backend/app/main.py
touch backend/app/emotion_service.py
touch backend/app/director_agent.py
touch backend/app/content_pipeline.py
touch backend/app/story_engine.py
touch backend/app/models.py
touch backend/requirements.txt
touch backend/tests/__init__.py
touch story.json
touch CLAUDE.md
touch .gitignore
```

### 0.2 Write CLAUDE.md (the master brain for all agents)

```markdown
# CLAUDE.md — Director's Cut Project

## Project Overview
An emotion-adaptive short film engine for the Gemini 3 Hackathon.
Webcam captures viewer facial expressions → Gemini Flash analyzes emotion →
Director Agent (Gemini Pro via LlamaIndex) decides next narrative branch →
Gemini Flash Image generates scene → Gemini TTS narrates → React frontend displays.

## Architecture
- **Backend:** Python 3.12, FastAPI, uvicorn
- **Frontend:** React + Vite (or plain HTML/JS)
- **AI Framework:** LlamaIndex Workflows + google-genai SDK
- **Models Used:**
  - Emotion detection: `gemini-3-flash` (media_resolution: low, thinking: none)
  - Director Agent: `gemini-3-pro-preview` (via llama-index-llms-google-genai)
  - Image generation: `gemini-2.5-flash-image` ($0.039/image — NOT Pro)
  - TTS narration: `gemini-2.5-flash-preview-tts`

## Module Specs
All module specs are in `docs/specs/`. Each module has typed Pydantic models in
`backend/app/models.py`. Implement against the spec, not vibes.

## Code Conventions
- All API models use Pydantic v2
- All endpoints use async
- Type hints everywhere — no `Any` types
- Error handling: every Gemini API call wrapped in try/except, return fallback on failure
- Env vars: GOOGLE_API_KEY (required), no hardcoded keys
- Image gen: ALWAYS use gemini-2.5-flash-image, NEVER nano-banana-pro (budget constraint)

## Git Conventions
- Commit after each module is working
- Commit messages: `feat(module): description` or `fix(module): description`
- Branch: main only (hackathon, no branching needed)

## Testing
- Unit tests: pytest, in backend/tests/
- Each module has a test file: test_emotion.py, test_director.py, test_pipeline.py
- Tests use mocked Gemini responses (don't burn API credits on tests)

## File References
- Story data: story.json (root)
- Module specs: docs/specs/m0_story.md, m1_emotion.md, m2_director.md, m3_pipeline.md, m4_frontend.md
- Pydantic models: backend/app/models.py

## Critical Budget Constraint
$25 total Gemini credits. ~$0.84 per full run. Do NOT use expensive models.
Do NOT make unnecessary API calls during development — use mocks.
```

### 0.3 Write requirements.txt

```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-dotenv>=1.0.0
google-genai>=1.0.0
llama-index>=0.12.0
llama-index-llms-google-genai>=0.4.0
llama-index-core>=0.12.0
pydantic>=2.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
httpx>=0.27.0
pillow>=10.0.0
```

### 0.4 Write the Pydantic models (backend/app/models.py)

```python
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

class StoryState(BaseModel):
    current_scene_id: str = "opening"
    scenes_played: list[str] = []
    current_chapter: str = "The Arrival"
    genre: str = "mystery"
```

### 0.5 Write spec docs (docs/specs/)

Copy each module spec from the previous artifact into individual markdown files:
- `docs/specs/m1_emotion.md`
- `docs/specs/m2_director.md`
- `docs/specs/m3_pipeline.md`
- `docs/specs/m4_frontend.md`

### 0.6 Initial commit

```bash
git add -A
git commit -m "feat(scaffold): project structure, CLAUDE.md, models, specs"
```

---

## STEP 1: CUSTOM SLASH COMMANDS

Create these in `.claude/commands/` tonight. They become your development workflow.

### `.claude/commands/implement.md`
```markdown
Implement the module described in the spec file: docs/specs/$ARGUMENTS

Follow this exact process:
1. Read the spec file completely
2. Read backend/app/models.py for the Pydantic types
3. Read CLAUDE.md for project conventions
4. Implement the module in the appropriate file(s)
5. Write a matching test file in backend/tests/
6. Run the tests with: cd backend && python -m pytest tests/ -v
7. If tests fail, fix the implementation and re-run
8. When all tests pass, report what was implemented

Use mocked Gemini API responses in tests — do NOT make real API calls in tests.
```

### `.claude/commands/fix.md`
```markdown
An error has occurred. Here is the context: $ARGUMENTS

Follow this exact process:
1. Read the error message / traceback carefully
2. Identify the root cause (don't guess — trace it)
3. Read the relevant source file(s)
4. Read the spec for this module in docs/specs/
5. Fix the issue while staying aligned with the spec
6. Run tests: cd backend && python -m pytest tests/ -v
7. If the fix introduces new failures, fix those too
8. Maximum 3 retry cycles. If still broken after 3, report what's wrong and stop.

Do NOT change the Pydantic models unless the spec explicitly requires it.
Do NOT add new dependencies without asking.
```

### `.claude/commands/commit.md`
```markdown
Review all uncommitted changes and create an appropriate git commit.

Process:
1. Run: git diff --stat
2. Run: git diff (to see actual changes)
3. Categorize changes by module (emotion, director, pipeline, frontend, config)
4. Write a commit message following the format: feat|fix|refactor(module): brief description
5. Stage only related files together — if changes span multiple modules, make separate commits
6. Execute: git add [files] && git commit -m "[message]"
7. Report what was committed

Never commit .env files, __pycache__, or node_modules.
```

### `.claude/commands/test.md`
```markdown
Run tests and analyze results for: $ARGUMENTS

Process:
1. If $ARGUMENTS is empty, run all tests: cd backend && python -m pytest tests/ -v
2. If $ARGUMENTS specifies a module, run: cd backend && python -m pytest tests/test_$ARGUMENTS.py -v
3. Analyze any failures:
   - Read the failing test
   - Read the implementation it tests
   - Read the spec in docs/specs/
   - Determine if the bug is in the test or the implementation
4. Fix the bug (in test or implementation, whichever is wrong)
5. Re-run and confirm pass
6. Report results
```

### `.claude/commands/e2e.md`
```markdown
Run an end-to-end test of the full pipeline.

Process:
1. Start the backend if not running: cd backend && uvicorn app.main:app --reload &
2. Test emotion endpoint: send a test image to POST /api/emotion
3. Test director endpoint: send a test EmotionSummary + StoryState to POST /api/director/decide
4. Test content pipeline: send a SceneDecision to POST /api/content/generate
5. Check that the frontend can load and display a scene
6. Report which steps passed and which failed
7. For any failures, read the error, read the spec, and fix

This burns real API credits. Only run when all unit tests pass.
```

### `.claude/commands/watchdog.md`
```markdown
Monitor the running application for errors and auto-fix them.

Process:
1. Read the most recent server logs (check terminal output or log file)
2. Identify any errors, warnings, or exceptions
3. For each error:
   a. Classify: API error, type error, import error, runtime error
   b. Read the source file where the error occurred
   c. Read the relevant spec
   d. Apply fix
   e. Verify fix doesn't break tests: cd backend && python -m pytest tests/ -v
4. Report all fixes applied

If an error involves Gemini API rate limits or credit issues, DO NOT retry.
Report the issue and suggest a workaround (mock, cache, etc.)
```

---

## STEP 2: CUSTOM SUBAGENTS

### `.claude/subagents/error-fixer.md`
```yaml
---
description: "Fixes errors and failing tests by tracing the root cause through logs, source code, and specs"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

You are the Error Fixer agent for the Director's Cut project.

When given an error, you:
1. TRACE: Read the full traceback. Identify the exact file and line.
2. CONTEXT: Read that file. Read the module spec in docs/specs/.
3. ROOT CAUSE: Identify whether it's a type error, logic error, import error, or API error.
4. FIX: Apply the minimal fix that aligns with the spec.
5. VERIFY: Run `cd backend && python -m pytest tests/ -v` to confirm.
6. REPORT: Return a one-paragraph summary of what was wrong and what you fixed.

Rules:
- Maximum 3 fix attempts per error. If still broken, report and stop.
- Never change models.py unless the spec requires it.
- Never add new pip dependencies.
- Never make real Gemini API calls — use mocks in tests.
```

### `.claude/subagents/test-writer.md`
```yaml
---
description: "Writes unit tests for modules based on their specs and Pydantic models"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

You are the Test Writer agent for the Director's Cut project.

When asked to write tests for a module:
1. Read the module spec in docs/specs/
2. Read the Pydantic models in backend/app/models.py
3. Read the current implementation
4. Write tests in backend/tests/test_{module}.py that cover:
   - Happy path with expected input → expected output
   - Edge cases (empty input, invalid emotion, missing fields)
   - Error handling (API failure → fallback behavior)
   - Type validation (outputs match Pydantic models)
5. Mock ALL Gemini API calls using unittest.mock.patch
6. Run the tests and fix any issues
7. Return a summary of tests written

Test style:
- Use pytest + pytest-asyncio
- Use unittest.mock.patch for API mocks
- Descriptive test names: test_emotion_reading_returns_valid_json
- Each test is independent — no shared state
```

### `.claude/subagents/committer.md`
```yaml
---
description: "Reviews changes and makes clean, incremental git commits"
allowed-tools: Read, Bash(git *), Grep, Glob
---

You are the Committer agent for the Director's Cut project.

When asked to commit:
1. Run `git status` and `git diff --stat`
2. Group changes by module
3. For each group, create a separate commit:
   - Stage only the relevant files
   - Write a message: feat|fix|refactor|test(module): description
4. Never commit: .env, __pycache__, node_modules, .pyc files
5. After committing, run `git log --oneline -5` and report

If there are uncommitted changes that look incomplete or broken,
flag them and do NOT commit. Report what looks unfinished.
```

---

## STEP 3: HACKATHON MORNING EXECUTION PLAN

### 3.1 Environment Setup (First 15 minutes at venue)

```bash
# Navigate to project
cd directors-cut

# Create and activate venv
python3.12 -m venv .venv
source .venv/bin/activate

# Install backend deps
cd backend && pip install -r requirements.txt && cd ..

# Set API key (from hackathon GCP credits)
echo "GOOGLE_API_KEY=your-key-here" > .env

# Verify Gemini works (one quick test)
python -c "
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client()
r = client.models.generate_content(model='gemini-3-flash', contents='Say hello')
print(r.text)
"

# Start tmux for Claude Code agent team
tmux new-session -s hackathon
```

### 3.2 Launch Claude Code as the Orchestrator

```bash
# In tmux, start Claude Code
claude

# First command — give it the lay of the land:
> Read CLAUDE.md, read all files in docs/specs/, read backend/app/models.py.
> Then tell me you're ready. We are building this in 7 hours.
```

### 3.3 Hour-by-Hour Agent Workflow

**HOUR 1 (9-10am): Scaffold + Verify**
```
YOU → Claude Code:
> /implement m1_emotion.md

Claude Code:
  → Reads spec
  → Implements emotion_service.py
  → Writes test_emotion.py (with mocked Gemini)
  → Runs tests
  → Reports results

YOU → Claude Code:
> /commit

Claude Code → committer subagent:
  → Stages emotion_service.py + test_emotion.py
  → Commits: "feat(emotion): implement emotion detection service with Flash"
```

**HOUR 2 (10-11am): Content Pipeline**
```
YOU → Claude Code:
> /implement m3_pipeline.md

[Same flow: implement → test → fix → commit]

YOU (in Cursor): review the diff, spot-check the Gemini model strings
```

**HOUR 3 (11-12pm): Director Agent**
```
YOU → Claude Code:
> /implement m2_director.md

[This is the most complex module — may need manual intervention]

If errors:
> /fix [paste the traceback]

Claude Code → error-fixer subagent:
  → Traces error, reads spec, fixes, re-tests
```

**HOUR 4 (12-1pm): Frontend**
```
YOU → Claude Code:
> /implement m4_frontend.md

Or if using Cursor for frontend (faster for React):
  Open Cursor → Cmd+K → "Create a React component that..."
  Use Cursor's inline AI for JSX generation
```

**HOUR 5 (1-2pm): Wire Everything**
```
YOU → Claude Code:
> Wire all modules together in backend/app/main.py.
> The FastAPI app should have these endpoints:
> - POST /api/emotion (takes base64 image, returns EmotionReading)
> - POST /api/director/decide (takes EmotionSummary + StoryState, returns SceneDecision)
> - POST /api/content/generate (takes SceneDecision, returns SceneAssets)
> - GET /api/story/scene/{scene_id} (returns SceneData from story.json)
> - WebSocket /ws/session (full loop: receives frames, pushes scenes)
> Read all module implementations first, then wire them.

Then: /e2e
```

**HOUR 6 (2-3pm): Integration + Polish**
```
YOU → Claude Code:
> /e2e

Fix whatever breaks. This is the first time you burn real API credits.

YOU → Claude Code:
> /watchdog  (after starting the app)

Run the full demo 2-3 times. Tune emotion thresholds.
```

**HOUR 7 (3-4pm): Demo Prep**
```
YOU → Claude Code:
> Write a comprehensive README.md for this project.
> Include: what it is, architecture diagram (ASCII), how to run,
> tech stack, Gemini models used, demo instructions.
> /commit

Record 1-min demo video. Submit.
```

---

## KEY PRINCIPLES

### 1. Spec → Implement → Test → Commit (never skip steps)
Every module goes through this cycle. The spec is the source of truth. If the implementation doesn't match the spec, the implementation is wrong.

### 2. Mocks during development, real API only for e2e
Unit tests ALWAYS mock Gemini. You only burn real credits during `/e2e` and final demo runs. This is how you stay under $25.

### 3. Claude Code orchestrates, Cursor assists
Claude Code handles the heavy multi-file implementations and automated test-fix loops. Cursor is for quick visual edits, reviewing diffs, and frontend work where inline AI is faster.

### 4. Subagents for specialized tasks, not everything
Use the error-fixer when something breaks. Use the test-writer when you need tests. Use the committer when you need clean commits. Don't over-engineer the agent setup — you have 7 hours.

### 5. If an agent is stuck for >5 minutes, intervene
You are the architect. If Claude Code is spinning on a fix, read the error yourself, make a judgment call, and course-correct. Don't let an agent waste 30 minutes on a config issue you could solve in 2 minutes.
