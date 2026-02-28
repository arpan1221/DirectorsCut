import json
import logging
import os

from google import genai
from google.genai import types

from app import story_engine
from app.models import EmotionSummary, Pacing, SceneDecision, StoryState

logger = logging.getLogger(__name__)

client = genai.Client()

_SYSTEM_PROMPT = (
    "You are the Director of an adaptive film called \"The Inheritance\".\n"
    "Pick the next story branch based on the viewer's emotional state and genre.\n\n"
    "Return ONLY a JSON object — no markdown, no explanation, no preamble:\n"
    '{"next_scene_id": "...", "mood_shift": "tense"|"warm"|"mysterious"|null, '
    '"pacing": "slow"|"medium"|"fast", "reasoning": "one sentence"}'
)


def _setup_phoenix() -> None:
    """Register direct Gemini spans → Phoenix tracing. Silently skipped if Phoenix is unreachable."""
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk import trace as trace_sdk
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = os.environ.get(
            "PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces"
        )
        tracer_provider = trace_sdk.TracerProvider()
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        logger.info("Phoenix tracing enabled → %s", endpoint)
    except Exception as exc:
        logger.warning("Phoenix tracing unavailable: %s", exc)


_setup_phoenix()


async def decide(
    emotion_summary: EmotionSummary,
    story_state: StoryState,
    story_data: dict,
) -> SceneDecision:
    current_scene = story_engine.get_scene(story_state.current_scene_id, story_data)

    # No next scene — stay put (ending reached)
    if current_scene.next is None:
        return SceneDecision(next_scene_id=story_state.current_scene_id)

    next_scene = story_engine.get_scene(current_scene.next, story_data)

    # Linear advance — no LLM call needed
    if not next_scene.is_decision_point:
        return SceneDecision(next_scene_id=next_scene.id)

    # Pre-compute fallback from emotion mapping
    valid_scenes = set(story_data.get("scenes", {}).keys())
    branches = story_engine.get_branches(next_scene)
    emotion_str = emotion_summary.dominant_emotion.value
    pre_selected = branches.get(emotion_str, branches.get("default", list(branches.values())[0]))

    try:
        genre = story_state.genre or "mystery"

        # Relay mode: all context injected in one shot — zero tool round-trips
        prompt = (
            f"Genre: {genre}\n"
            f"Decision point: '{next_scene.id}'\n"
            f"Available branches: {json.dumps(branches)}\n"
            f"Viewer emotional state: {emotion_summary.model_dump_json()}\n"
            f"Scenes played: {', '.join(story_state.scenes_played) or 'none'}\n"
            f"Emotion-mapped default: {pre_selected}\n\n"
            f"Choose the branch that creates the most compelling {genre} experience for this viewer."
        )

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.8,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        raw = (response.text or "").strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)

        chosen_id = data.get("next_scene_id", pre_selected)
        if chosen_id not in valid_scenes:
            logger.warning(f"Director returned unknown scene '{chosen_id}', using '{pre_selected}'")
            chosen_id = pre_selected

        return SceneDecision(
            next_scene_id=chosen_id,
            mood_shift=data.get("mood_shift"),
            pacing=Pacing(data.get("pacing", "medium")),
            reasoning=data.get("reasoning", ""),
        )

    except Exception as e:
        logger.error(f"Director agent failed: {e}")
        return SceneDecision(next_scene_id=pre_selected)
