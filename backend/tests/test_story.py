import pytest

from app.models import SceneData, StoryState
from app.story_engine import advance, get_branches, get_scene, load_story


def test_load_story_returns_dict(story_data):
    assert "scenes" in story_data
    assert isinstance(story_data["scenes"], dict)


def test_get_scene_valid_id(story_data):
    scene = get_scene("opening", story_data)
    assert isinstance(scene, SceneData)
    assert scene.id == "opening"
    assert scene.chapter == "The Arrival"


def test_get_scene_invalid_id(story_data):
    with pytest.raises(ValueError):
        get_scene("nonexistent_scene_xyz", story_data)


def test_get_branches_decision_point(story_data):
    scene = get_scene("decision_1", story_data)
    branches = get_branches(scene)
    assert isinstance(branches, dict)
    assert "engaged" in branches
    assert "default" in branches


def test_get_branches_non_decision_point(story_data):
    scene = get_scene("opening", story_data)
    with pytest.raises(ValueError):
        get_branches(scene)


def test_advance_state():
    state = StoryState(
        current_scene_id="opening",
        scenes_played=[],
        current_chapter="The Arrival",
        genre="mystery",
    )
    new_state = advance(state, "foyer")
    assert new_state.current_scene_id == "foyer"
    assert "opening" in new_state.scenes_played
    assert len(new_state.scenes_played) == 1
