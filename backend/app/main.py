import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import content_pipeline, director_agent, emotion_service, story_engine
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
sessions: dict[int, tuple[StoryState, EmotionAccumulator, int]] = {}


# ---------------------------------------------------------------------------
# Lifespan — load story.json once at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    global story_data
    story_path = Path(__file__).parent.parent.parent / "story.json"
    story_data = story_engine.load_story(str(story_path))
    logger.info(f"Loaded story with {len(story_data.get('scenes', {}))} scenes")
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Director's Cut API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    return await emotion_service.analyze_frame(body.image_base64)


@app.post("/api/director/decide")
async def post_director_decide(summary: EmotionSummary) -> SceneDecision:
    global _rest_state
    return await director_agent.decide(summary, _rest_state, story_data)


@app.post("/api/content/generate")
async def post_content_generate(req: GenerateRequest) -> SceneAssets:
    return await content_pipeline.generate_scene(req.decision, req.scene)


@app.get("/api/story/scene/{scene_id}")
async def get_story_scene(scene_id: str) -> SceneData:
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
    return _rest_state


# ---------------------------------------------------------------------------
# WebSocket /ws/session
# ---------------------------------------------------------------------------


async def _send_opening_scene(
    websocket: WebSocket,
    state: StoryState,
    accumulator: EmotionAccumulator,
) -> tuple[StoryState, int]:
    """Generate and send the opening scene. Returns updated state and reset frame_count=0."""
    opening_scene = story_engine.get_scene("opening", story_data)
    decision = SceneDecision(next_scene_id="opening")
    assets = await content_pipeline.generate_scene(decision, opening_scene)
    await websocket.send_text(
        json.dumps({"type": "scene", "assets": assets.model_dump()})
    )
    return state, 0


@app.websocket("/ws/session")
async def ws_session(websocket: WebSocket) -> None:
    await websocket.accept()

    # Initialise per-session state
    state = StoryState()
    accumulator = EmotionAccumulator()
    frame_count = 0
    sessions[id(websocket)] = (state, accumulator, frame_count)

    try:
        # Send opening scene immediately on connect
        state, frame_count = await _send_opening_scene(websocket, state, accumulator)
        sessions[id(websocket)] = (state, accumulator, frame_count)

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
                state, frame_count = await _send_opening_scene(websocket, state, accumulator)
                sessions[id(websocket)] = (state, accumulator, frame_count)

            # ----------------------------------------------------------------
            # "reset" — same as start but keep genre
            # ----------------------------------------------------------------
            elif msg_type == "reset":
                state = StoryState(genre=state.genre)
                accumulator = EmotionAccumulator()
                frame_count = 0
                state, frame_count = await _send_opening_scene(websocket, state, accumulator)
                sessions[id(websocket)] = (state, accumulator, frame_count)

            # ----------------------------------------------------------------
            # "frame" — analyze emotion, maybe advance to next scene
            # ----------------------------------------------------------------
            elif msg_type == "frame":
                frame_b64 = msg.get("data", "")

                # Analyze emotion from frame
                reading: EmotionReading = await emotion_service.analyze_frame(frame_b64)
                await websocket.send_text(
                    json.dumps({"type": "emotion", "data": reading.model_dump()})
                )
                accumulator.add_reading(reading)
                frame_count += 1
                sessions[id(websocket)] = (state, accumulator, frame_count)

                # Check if it's time to advance
                current_scene = story_engine.get_scene(state.current_scene_id, story_data)
                frames_needed = max(1, current_scene.duration_seconds // 8)

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

                    # Generate image + audio in parallel
                    assets = await content_pipeline.generate_scene(decision, new_scene)
                    frame_count = 0
                    sessions[id(websocket)] = (state, accumulator, frame_count)

                    await websocket.send_text(
                        json.dumps({"type": "scene", "assets": assets.model_dump()})
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
        except Exception:
            pass
    finally:
        sessions.pop(id(websocket), None)
