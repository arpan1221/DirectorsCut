import json
import logging

from google import genai
from google.genai import types

from app import story_engine
from app.models import EmotionSummary, Pacing, SceneDecision, StoryState

logger = logging.getLogger(__name__)

client = genai.Client()


async def decide(
    emotion_summary: EmotionSummary,
    story_state: StoryState,
    story_data: dict,
) -> SceneDecision:
    current_scene = story_engine.get_scene(story_state.current_scene_id, story_data)

    if current_scene.next is None:
        return SceneDecision(next_scene_id=story_state.current_scene_id)

    next_scene = story_engine.get_scene(current_scene.next, story_data)

    if not next_scene.is_decision_point:
        return SceneDecision(next_scene_id=next_scene.id)

    # Decision point — map emotion to branch then optionally call Gemini Pro
    adaptation_rules = story_engine.get_branches(next_scene)
    emotion_str = emotion_summary.dominant_emotion.value
    pre_selected = adaptation_rules.get(
        emotion_str, adaptation_rules.get("default", list(adaptation_rules.values())[0])
    )

    try:
        system_prompt = (
            "You are the Director of an adaptive mystery film called \"The Inheritance\".\n"
            "You are making a narrative decision based on the viewer's emotional state.\n\n"
            f"Story so far: {', '.join(story_state.scenes_played) or 'just started'}\n"
            f"Current viewer state: {emotion_summary.model_dump_json()}\n"
            f"Available branches: {json.dumps(adaptation_rules)}\n"
            f"Emotion-mapped branch: {pre_selected}\n\n"
            "Confirm or override the branch selection. Return ONLY JSON:\n"
            '{"next_scene_id": "the scene id you choose", '
            '"mood_shift": "tense" or "warm" or "mysterious" or null, '
            '"pacing": "slow" or "medium" or "fast", '
            '"reasoning": "One sentence explaining your choice"}'
        )
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=system_prompt,
            config=types.GenerateContentConfig(temperature=0.8),
        )
        data = json.loads(response.text)
        return SceneDecision(
            next_scene_id=data.get("next_scene_id", pre_selected),
            mood_shift=data.get("mood_shift"),
            pacing=Pacing(data.get("pacing", "medium")),
            reasoning=data.get("reasoning", ""),
        )
    except Exception as e:
        logger.error(f"Director Gemini call failed: {e}")
        return SceneDecision(next_scene_id=pre_selected)
