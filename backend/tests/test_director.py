import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.director_agent import decide
from app.models import EmotionSummary, EmotionType, SceneDecision, StoryState


def make_summary(emotion: str = "engaged") -> EmotionSummary:
    return EmotionSummary(
        dominant_emotion=EmotionType(emotion),
        trend="stable",
        intensity_avg=7.0,
        attention_score=0.9,
        volatility=1.0,
        reading_count=5,
    )


def mock_workflow_response(next_scene_id: str = "upstairs_door") -> MagicMock:
    """Return a mock AgentWorkflow whose run() yields a proper director JSON response."""
    mock_output = MagicMock()
    mock_output.response.content = json.dumps({
        "next_scene_id": next_scene_id,
        "mood_shift": "tense",
        "pacing": "medium",
        "reasoning": "Viewer is engaged, deepening the mystery.",
    })
    mock_workflow = MagicMock()
    mock_workflow.run = AsyncMock(return_value=mock_output)
    return mock_workflow


async def test_decide_non_decision_point(story_data):
    # opening.next = "foyer" which is NOT a decision point — workflow never called
    state = StoryState(
        current_scene_id="opening",
        scenes_played=[],
        current_chapter="The Arrival",
        genre="mystery",
    )
    with patch("app.director_agent._get_workflow") as mock_get_workflow:
        decision = await decide(make_summary(), state, story_data)
    mock_get_workflow.assert_not_called()
    assert isinstance(decision, SceneDecision)
    assert decision.next_scene_id == "foyer"


async def test_decide_at_decision_point_calls_workflow(story_data):
    # sound_upstairs.next = "decision_1" which IS a decision point
    state = StoryState(
        current_scene_id="sound_upstairs",
        scenes_played=["opening", "foyer"],
        current_chapter="The Arrival",
        genre="mystery",
    )
    mock_workflow = mock_workflow_response("upstairs_door")
    with patch("app.director_agent._get_workflow", return_value=mock_workflow):
        decision = await decide(make_summary("engaged"), state, story_data)
    mock_workflow.run.assert_called_once()
    assert isinstance(decision, SceneDecision)
    assert decision.next_scene_id == "upstairs_door"
    assert decision.reasoning != ""


async def test_decide_fallback_on_workflow_failure(story_data):
    state = StoryState(
        current_scene_id="sound_upstairs",
        scenes_played=[],
        current_chapter="The Arrival",
        genre="mystery",
    )
    mock_workflow = MagicMock()
    mock_workflow.run = AsyncMock(side_effect=Exception("LlamaIndex down"))
    with patch("app.director_agent._get_workflow", return_value=mock_workflow):
        decision = await decide(make_summary("engaged"), state, story_data)
    assert isinstance(decision, SceneDecision)
    # "engaged" → "upstairs_door" per decision_1 adaptation_rules
    assert decision.next_scene_id == "upstairs_door"


async def test_decide_uses_default_when_no_emotion_match(story_data):
    # Custom story data with sparse adaptation_rules (no "engaged" key)
    custom_data = {
        "scenes": {
            "scene_a": {
                "id": "scene_a",
                "chapter": "Ch",
                "image_prompt": "",
                "narration": "",
                "duration_seconds": 15,
                "next": "branch_point",
                "is_decision_point": False,
                "adaptation_rules": None,
            },
            "branch_point": {
                "id": "branch_point",
                "chapter": "Ch",
                "image_prompt": "",
                "narration": "",
                "duration_seconds": 0,
                "next": None,
                "is_decision_point": True,
                "adaptation_rules": {
                    "bored": "slow_scene",
                    "default": "default_scene",
                },
            },
            "slow_scene": {
                "id": "slow_scene", "chapter": "Ch", "image_prompt": "", "narration": "",
                "duration_seconds": 16, "next": None, "is_decision_point": False, "adaptation_rules": None,
            },
            "default_scene": {
                "id": "default_scene", "chapter": "Ch", "image_prompt": "", "narration": "",
                "duration_seconds": 16, "next": None, "is_decision_point": False, "adaptation_rules": None,
            },
        }
    }
    state = StoryState(
        current_scene_id="scene_a", scenes_played=[], current_chapter="Ch", genre="mystery"
    )
    mock_workflow = MagicMock()
    mock_workflow.run = AsyncMock(side_effect=Exception("skip workflow"))
    with patch("app.director_agent._get_workflow", return_value=mock_workflow):
        decision = await decide(make_summary("engaged"), state, custom_data)
    # "engaged" not in adaptation_rules → falls back to "default" key
    assert decision.next_scene_id == "default_scene"
