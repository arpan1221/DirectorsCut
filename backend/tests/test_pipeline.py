from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.content_pipeline import _cache, generate_scene
from app.models import Pacing, SceneAssets, SceneData, SceneDecision


@pytest.fixture(autouse=True)
def clear_pipeline_cache():
    _cache.clear()
    yield
    _cache.clear()


def make_scene(scene_id: str = "test_scene") -> SceneData:
    return SceneData(
        id=scene_id,
        chapter="The Arrival",
        image_prompt="A dark Victorian mansion at dusk",
        narration="The letter arrived three days ago.",
        duration_seconds=18,
        next="foyer",
        is_decision_point=False,
    )


def make_decision() -> SceneDecision:
    return SceneDecision(next_scene_id="foyer", mood_shift="tense", pacing=Pacing.MEDIUM)


def mock_image_response() -> MagicMock:
    m = MagicMock()
    m.candidates[0].content.parts[0].inline_data.data = "base64imagedata"
    return m


def mock_audio_response() -> MagicMock:
    m = MagicMock()
    m.candidates[0].content.parts[0].inline_data.data = "base64audiodata"
    return m


async def test_generate_scene_returns_assets():
    scene = make_scene()
    decision = make_decision()
    with patch("app.content_pipeline.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_image_response(),
            mock_audio_response(),
        ])
        assets = await generate_scene(decision, scene)
    assert isinstance(assets, SceneAssets)
    assert assets.scene_id == scene.id
    assert assets.image_base64 == "base64imagedata"
    assert assets.audio_base64 == "base64audiodata"
    assert assets.narration_text == scene.narration


async def test_generate_scene_image_fallback():
    scene = make_scene()
    decision = make_decision()

    def side_effect(model, **kwargs):
        if "tts" not in model:  # image model — force failure
            raise Exception("Image API down")
        return mock_audio_response()

    with patch("app.content_pipeline.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)
        assets = await generate_scene(decision, scene)
    assert assets.image_base64 is None
    assert assets.audio_base64 == "base64audiodata"


async def test_generate_scene_tts_fallback():
    scene = make_scene()
    decision = make_decision()

    def side_effect(model, **kwargs):
        if "tts" in model:  # TTS model — force failure
            raise Exception("TTS API down")
        return mock_image_response()

    with patch("app.content_pipeline.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)
        assets = await generate_scene(decision, scene)
    assert assets.image_base64 == "base64imagedata"
    assert assets.audio_base64 is None


async def test_generate_scene_cache_hit():
    scene = make_scene()
    decision = make_decision()
    with patch("app.content_pipeline.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_image_response(),
            mock_audio_response(),
        ])
        first = await generate_scene(decision, scene)
        second = await generate_scene(decision, scene)
    # Only 2 API calls total (image + audio) for first call; second is cached
    assert mock_client.aio.models.generate_content.call_count == 2
    assert first is second


async def test_generate_scene_parallel():
    scene = make_scene()
    decision = make_decision()
    with patch("app.content_pipeline.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_image_response(),
            mock_audio_response(),
        ])
        assets = await generate_scene(decision, scene)
    # asyncio.gather fires both calls; verify both returned successfully
    assert assets.image_base64 is not None
    assert assets.audio_base64 is not None
    assert mock_client.aio.models.generate_content.call_count == 2
