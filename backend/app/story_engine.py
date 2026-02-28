import json

from app.models import SceneData, StoryState


def load_story(path: str) -> dict:
    with open(path) as f:
        data = json.load(f)
    if "scenes" not in data:
        raise ValueError(f"Invalid story.json at '{path}': missing 'scenes' key")
    return data


def get_scene(scene_id: str, story_data: dict) -> SceneData:
    scenes = story_data.get("scenes", {})
    if scene_id not in scenes:
        raise ValueError(f"Scene '{scene_id}' not found in story data")
    return SceneData(**scenes[scene_id])


def get_branches(scene: SceneData) -> dict[str, str]:
    if not scene.is_decision_point or scene.adaptation_rules is None:
        raise ValueError(f"Scene '{scene.id}' is not a decision point")
    return scene.adaptation_rules


def advance(story_state: StoryState, next_scene_id: str) -> StoryState:
    scenes_played = story_state.scenes_played + [story_state.current_scene_id]
    return StoryState(
        current_scene_id=next_scene_id,
        scenes_played=scenes_played,
        current_chapter=story_state.current_chapter,
        genre=story_state.genre,
    )
