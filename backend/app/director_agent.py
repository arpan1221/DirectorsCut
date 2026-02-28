import json
import logging
import os

from llama_index.core.agent import AgentWorkflow, FunctionAgent
from llama_index.core.tools import FunctionTool
from llama_index.llms.google_genai import GoogleGenAI

from app import story_engine
from app.models import EmotionSummary, Pacing, SceneDecision, StoryState

logger = logging.getLogger(__name__)

# Module-level story reference — refreshed each call so tool closures always see current data
_story_data: dict = {}

# Lazy singleton workflow — created once after load_dotenv() has run
_workflow: AgentWorkflow | None = None

_SYSTEM_PROMPT_TEMPLATE = """You are the Director of an adaptive {genre} film called "The Inheritance".
You decide which narrative branch to take at story decision points based on the viewer's emotional state. Lean into {genre} genre conventions and atmosphere in your decision-making.

You have two tools:
- get_scene(scene_id): returns full scene details (narration, chapter, image prompt, next scene)
- get_branches(decision_scene_id): returns all available narrative branches at a decision point

Your process:
1. Call get_branches() on the decision point scene ID you are given
2. Read the viewer's emotional state and story history
3. Choose the branch that creates the most compelling {genre} experience for this specific viewer
4. Return ONLY a JSON object — no markdown, no explanation, no preamble:
{{"next_scene_id": "...", "mood_shift": "tense"|"warm"|"mysterious"|null, "pacing": "slow"|"medium"|"fast", "reasoning": "one sentence"}}\""""

_SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(genre="mystery")


def _get_workflow(genre: str = "mystery") -> AgentWorkflow:
    global _workflow
    # Rebuild workflow if genre changed (allows genre switching per session)
    if _workflow is not None and getattr(_workflow, "_genre", None) == genre:
        return _workflow

    llm = GoogleGenAI(
        model="gemini-2.5-pro",
        api_key=os.environ.get("GOOGLE_API_KEY", ""),
        temperature=1.0,
    )

    def get_scene(scene_id: str) -> str:
        """Get full details of a scene by ID: narration, image prompt, chapter, and what comes next."""
        try:
            scene = story_engine.get_scene(scene_id, _story_data)
            return scene.model_dump_json()
        except ValueError as e:
            return f"Error: {e}"

    def get_branches(decision_scene_id: str) -> str:
        """Get the available narrative branches at a decision point. Returns a JSON mapping of emotion states to next scene IDs."""
        try:
            scene = story_engine.get_scene(decision_scene_id, _story_data)
            return json.dumps(story_engine.get_branches(scene))
        except ValueError as e:
            return f"Error: {e}"

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(genre=genre)

    agent = FunctionAgent(
        name="Director",
        description=f"Narrative director for a {genre} film that picks the next story branch based on viewer emotion",
        system_prompt=system_prompt,
        tools=[
            FunctionTool.from_defaults(fn=get_scene),
            FunctionTool.from_defaults(fn=get_branches),
        ],
        llm=llm,
        verbose=False,
    )

    _workflow = AgentWorkflow(agents=[agent], root_agent="Director")
    _workflow._genre = genre  # type: ignore[attr-defined]
    return _workflow


async def decide(
    emotion_summary: EmotionSummary,
    story_state: StoryState,
    story_data: dict,
) -> SceneDecision:
    global _story_data
    _story_data = story_data  # refresh so tool closures see current story

    current_scene = story_engine.get_scene(story_state.current_scene_id, story_data)

    # No next scene — stay put (ending reached)
    if current_scene.next is None:
        return SceneDecision(next_scene_id=story_state.current_scene_id)

    next_scene = story_engine.get_scene(current_scene.next, story_data)

    # Linear advance — no agent call needed
    if not next_scene.is_decision_point:
        return SceneDecision(next_scene_id=next_scene.id)

    # Build fallback from emotion mapping in case agent fails
    valid_scenes = set(story_data.get("scenes", {}).keys())
    adaptation_rules = story_engine.get_branches(next_scene)
    emotion_str = emotion_summary.dominant_emotion.value
    pre_selected = adaptation_rules.get(
        emotion_str, adaptation_rules.get("default", list(adaptation_rules.values())[0])
    )

    try:
        genre = story_state.genre or "mystery"
        workflow = _get_workflow(genre)

        prompt = (
            f"You are at decision point '{next_scene.id}'.\n\n"
            f"Genre: {genre}\n"
            f"Viewer emotional state: {emotion_summary.model_dump_json()}\n"
            f"Scenes played so far: {', '.join(story_state.scenes_played) or 'none yet'}\n"
            f"Simple emotion-mapped branch (your starting point): {pre_selected}\n\n"
            f"Call get_branches('{next_scene.id}') to see all options, "
            f"then return your JSON decision."
        )

        handler = workflow.run(user_msg=prompt)
        output = await handler

        raw = (output.response.content or "").strip()
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
