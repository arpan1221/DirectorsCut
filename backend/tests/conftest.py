import os

# Set dummy API key before any app module imports to prevent genai.Client() from failing
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-key-for-unit-tests")

import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def sample_emotion_json():
    return {
        "primary_emotion": "engaged",
        "intensity": 7,
        "attention": "screen",
        "confidence": 0.85,
    }


@pytest.fixture
def sample_emotion_json_tense():
    return {
        "primary_emotion": "tense",
        "intensity": 8,
        "attention": "screen",
        "confidence": 0.9,
    }


@pytest.fixture
def sample_emotion_json_bored():
    return {
        "primary_emotion": "bored",
        "intensity": 3,
        "attention": "away",
        "confidence": 0.7,
    }


@pytest.fixture
def mock_gemini_emotion_response(sample_emotion_json):
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(sample_emotion_json)
    return mock_resp


@pytest.fixture
def mock_gemini_director_response():
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "next_scene_id": "upstairs_door",
        "mood_shift": "tense",
        "pacing": "medium",
        "reasoning": "Viewer is engaged, deepening the mystery.",
    })
    return mock_resp


@pytest.fixture
def story_data():
    story_path = Path(__file__).parent.parent.parent / "story.json"
    with open(story_path) as f:
        return json.load(f)


@pytest.fixture
def fake_frame_base64():
    # 1x1 white pixel JPEG as base64 (valid but tiny image)
    return "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAFBABAAAAAAAAAAAAAAAAAAAACf/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKgA/9k="
