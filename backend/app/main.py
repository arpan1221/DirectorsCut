import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Must run before app modules are imported — genai.Client() reads GOOGLE_API_KEY at instantiation
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import content_pipeline, director_agent, emotion_service, narrator_agent, story_engine
from app.emotion_service import EmotionAccumulator
from app.models import (
    EmotionReading,
    EmotionSummary,
    FrameInput,
    SceneAssets,
    SceneData,
    SceneDecision,
    StoryState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level globals
# ---------------------------------------------------------------------------
story_data: dict = {}
_rest_state: StoryState = StoryState()
# 4-tuple: (state, accumulator, frame_count, prefetch_task)
# prefetch_task fires Veo generation for the *next* linear scene immediately after
# the current scene starts, so the video is ready before the scene transition.
sessions: dict[int, tuple[StoryState, EmotionAccumulator, int, "asyncio.Task[SceneAssets | None] | None"]] = {}
_story_ready = asyncio.Event()


# ---------------------------------------------------------------------------
# Lifespan — load story.json once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global story_data
    story_path = Path(__file__).parent.parent.parent / "story.json"
    story_data = story_engine.load_story(str(story_path))
    logger.info(f"Loaded story with {len(story_data.get('scenes', {}))} scenes")
    _story_ready.set()
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Director's Cut API", lifespan=lifespan)

# Restrict CORS to known frontends; fall back to env var for deployed environments
_allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

# Mount frontend static files if the directory exists
_frontend_dir = Path(__file__).parent.parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_dir), html=True), name="static")


# ---------------------------------------------------------------------------
# Inline request wrapper (models.py is locked — define here)
# ---------------------------------------------------------------------------
class GenerateRequest(BaseModel):
    decision: SceneDecision
    scene: SceneData


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/emotion")
async def post_emotion(body: FrameInput) -> EmotionReading:
    await _story_ready.wait()
    return await emotion_service.analyze_frame(body.image_base64)


@app.post("/api/director/decide")
async def post_director_decide(summary: EmotionSummary) -> SceneDecision:
    global _rest_state
    await _story_ready.wait()
    return await director_agent.decide(summary, _rest_state, story_data)


@app.post("/api/content/generate")
async def post_content_generate(req: GenerateRequest) -> SceneAssets:
    return await content_pipeline.generate_scene(req.decision, req.scene)


@app.get("/api/story/scene/{scene_id}")
async def get_story_scene(scene_id: str) -> SceneData:
    await _story_ready.wait()
    try:
        return story_engine.get_scene(scene_id, story_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/story/state")
async def get_story_state() -> StoryState:
    return _rest_state


@app.post("/api/story/reset")
async def post_story_reset() -> StoryState:
    global _rest_state
    _rest_state = StoryState()
    content_pipeline.clear_cache()
    return _rest_state


# ---------------------------------------------------------------------------
# WebSocket /ws/session
# ---------------------------------------------------------------------------


async def _prefetch_next(scene: SceneData, genre: str) -> "SceneAssets | None":
    """Pre-generate the next *linear* scene's assets while the current one plays.

    Only fires for non-decision, non-ending next scenes.  At decision points we
    don't know the branch yet, so we skip.  The result lands in the cache so the
    transition handler finds it instantly.
    """
    if scene.next is None:
        return None
    try:
        next_node = story_engine.get_scene(scene.next, story_data)
    except ValueError:
        return None
    if next_node.is_decision_point:
        return None
    dummy_decision = SceneDecision(next_scene_id=next_node.id)
    try:
        return await content_pipeline.generate_scene(dummy_decision, next_node, genre=genre)
    except Exception as e:
        logger.warning(f"Prefetch failed for scene '{next_node.id}': {e}")
        return None


async def _generate_with_narrator(
    decision: SceneDecision,
    scene: SceneData,
    accumulator: EmotionAccumulator,
    state: StoryState,
) -> SceneAssets:
    """Run Narrator Agent to personalise narration, then generate scene assets."""
    genre = state.genre or "mystery"
    if accumulator.history and scene.narration:
        adapted = await narrator_agent.adapt_narration(
            seed=scene.narration,
            mood=decision.mood_shift,
            pacing=decision.pacing.value,
            emotion=accumulator.get_summary(),
            scenes_played=state.scenes_played,
            genre=genre,
        )
        decision = decision.model_copy(update={"override_narration": adapted})
    return await content_pipeline.generate_scene(decision, scene, genre=genre)


async def _send_opening_scene(
    websocket: WebSocket,
    state: StoryState,
    accumulator: EmotionAccumulator,
) -> tuple[StoryState, int, "asyncio.Task[SceneAssets | None] | None"]:
    """Generate and send the opening scene.

    Returns (state, frame_count=0, prefetch_task) where prefetch_task has
    already started generating the next linear scene's assets.
    """
    genre = state.genre or "mystery"
    opening_scene = story_engine.get_scene("opening", story_data)
    decision = SceneDecision(next_scene_id="opening")
    assets = await content_pipeline.generate_scene(decision, opening_scene, genre=genre)
    await websocket.send_text(
        json.dumps({"type": "scene", "assets": assets.model_dump(mode="json")})
    )
    prefetch_task = asyncio.create_task(_prefetch_next(opening_scene, genre))
    return state, 0, prefetch_task


@app.websocket("/ws/session")
async def ws_session(websocket: WebSocket) -> None:
    await websocket.accept()
    await _story_ready.wait()

    # Initialise per-session state
    state = StoryState()
    accumulator = EmotionAccumulator()
    frame_count = 0
    prefetch_task: "asyncio.Task[SceneAssets | None] | None" = None
    sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

    try:
        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("WS received non-JSON message, ignoring")
                continue

            msg_type = msg.get("type", "")

            # ----------------------------------------------------------------
            # "start" — reset session and re-send opening
            # ----------------------------------------------------------------
            if msg_type == "start":
                genre = msg.get("genre", "mystery")
                state = StoryState(genre=genre)
                accumulator = EmotionAccumulator()
                frame_count = 0
                content_pipeline.clear_cache()
                state, frame_count, prefetch_task = await _send_opening_scene(websocket, state, accumulator)
                sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

            # ----------------------------------------------------------------
            # "reset" — same as start but keep genre
            # ----------------------------------------------------------------
            elif msg_type == "reset":
                state = StoryState(genre=state.genre)
                accumulator = EmotionAccumulator()
                frame_count = 0
                content_pipeline.clear_cache()
                state, frame_count, prefetch_task = await _send_opening_scene(websocket, state, accumulator)
                sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

            # ----------------------------------------------------------------
            # "emotion" — pre-computed reading from Gemini Live API (React)
            # Treated identically to "frame" after analysis step
            # ----------------------------------------------------------------
            elif msg_type == "emotion":
                reading = EmotionReading(**msg["data"])
                # Echo back for UI display (same protocol as frame path)
                await websocket.send_text(
                    json.dumps({"type": "emotion", "data": reading.model_dump(mode="json")})
                )
                accumulator.add_reading(reading)
                frame_count += 1
                sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

                current_scene = story_engine.get_scene(state.current_scene_id, story_data)
                frames_needed = max(1, current_scene.duration_seconds // 15)

                if frame_count >= frames_needed and current_scene.next is not None:
                    next_node = story_engine.get_scene(current_scene.next, story_data)
                    if next_node.is_decision_point:
                        await websocket.send_text(json.dumps({"type": "deciding"}))
                        decision = await director_agent.decide(
                            accumulator.get_summary(), state, story_data
                        )
                    else:
                        decision = SceneDecision(next_scene_id=next_node.id)

                    state = story_engine.advance(state, decision.next_scene_id)
                    new_scene = story_engine.get_scene(decision.next_scene_id, story_data)
                    assets = await _generate_with_narrator(decision, new_scene, accumulator, state)
                    frame_count = 0
                    # Kick off prefetch for the next linear scene immediately
                    prefetch_task = asyncio.create_task(
                        _prefetch_next(new_scene, state.genre or "mystery")
                    )
                    sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

                    await websocket.send_text(
                        json.dumps({"type": "scene", "assets": assets.model_dump(mode="json")})
                    )
                    if new_scene.next is None and not new_scene.is_decision_point:
                        await websocket.send_text(
                            json.dumps({
                                "type": "complete",
                                "ending": new_scene.id,
                                "scenes_played": state.scenes_played,
                            })
                        )

            # ----------------------------------------------------------------
            # "frame" — analyze emotion, maybe advance to next scene
            # ----------------------------------------------------------------
            elif msg_type == "frame":
                frame_b64 = msg.get("data", "")

                # Analyze emotion from frame
                reading: EmotionReading = await emotion_service.analyze_frame(frame_b64)
                await websocket.send_text(
                    json.dumps({"type": "emotion", "data": reading.model_dump(mode="json")})
                )
                accumulator.add_reading(reading)
                frame_count += 1
                sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

                # Check if it's time to advance
                current_scene = story_engine.get_scene(state.current_scene_id, story_data)
                frames_needed = max(1, current_scene.duration_seconds // 15)

                if frame_count >= frames_needed and current_scene.next is not None:
                    next_node = story_engine.get_scene(current_scene.next, story_data)

                    # Decision point — run director to get real destination
                    if next_node.is_decision_point:
                        await websocket.send_text(json.dumps({"type": "deciding"}))
                        decision = await director_agent.decide(
                            accumulator.get_summary(), state, story_data
                        )
                    else:
                        # Linear advance — no director call needed
                        decision = SceneDecision(next_scene_id=next_node.id)

                    # Advance state to the chosen scene
                    state = story_engine.advance(state, decision.next_scene_id)
                    new_scene = story_engine.get_scene(decision.next_scene_id, story_data)

                    # Narrator adapts narration, then content pipeline generates video/image + audio
                    assets = await _generate_with_narrator(decision, new_scene, accumulator, state)
                    frame_count = 0
                    # Kick off prefetch for the next linear scene immediately
                    prefetch_task = asyncio.create_task(
                        _prefetch_next(new_scene, state.genre or "mystery")
                    )
                    sessions[id(websocket)] = (state, accumulator, frame_count, prefetch_task)

                    await websocket.send_text(
                        json.dumps({"type": "scene", "assets": assets.model_dump(mode="json")})
                    )

                    # Ending detection: next is None and not a decision point
                    if new_scene.next is None and not new_scene.is_decision_point:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "complete",
                                    "ending": new_scene.id,
                                    "scenes_played": state.scenes_played,
                                }
                            )
                        )

    except WebSocketDisconnect:
        logger.info(f"WS session {id(websocket)} disconnected")
    except Exception as e:
        logger.error(f"WS session {id(websocket)} error: {e}", exc_info=True)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Internal server error"})
            )
        except Exception as send_err:
            logger.warning(f"WS session {id(websocket)} failed to send error: {send_err}")
    finally:
        sessions.pop(id(websocket), None)
