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


def mock_veo_operation(video_bytes: bytes = b"fakevideobytes") -> MagicMock:
    """Return a mock Veo operation that is immediately done."""
    op = MagicMock()
    op.done = True
    op.response.generated_videos[0].video.fetch.return_value = video_bytes
    return op


# ---------------------------------------------------------------------------
# Veo-enabled tests (VEO_ENABLED=true)
# ---------------------------------------------------------------------------

async def test_generate_scene_veo_returns_video():
    """When Veo succeeds, video_base64 is set and image_base64 is None."""
    scene = make_scene()
    decision = make_decision()
    op = mock_veo_operation(b"fakevideobytes")

    async def fake_to_thread(fn, *args, **kwargs):
        """Simulate asyncio.to_thread: call fn synchronously for test purposes."""
        return fn(*args, **kwargs)

    with (
        patch("app.content_pipeline._VEO_ENABLED", True),
        patch("app.content_pipeline.client") as mock_client,
        patch("app.content_pipeline.asyncio.to_thread", side_effect=fake_to_thread),
    ):
        mock_client.models.generate_videos.return_value = op
        mock_client.operations.get.return_value = op
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_audio_response())
        assets = await generate_scene(decision, scene)
    assert isinstance(assets, SceneAssets)
    assert assets.video_base64 is not None
    assert assets.image_base64 is None         # no static image when Veo succeeds
    assert assets.audio_base64 == "base64audiodata"


async def test_generate_scene_veo_failure_falls_back_to_image():
    """When Veo fails, image_base64 is set via the static image fallback."""
    scene = make_scene()
    decision = make_decision()
    with (
        patch("app.content_pipeline._VEO_ENABLED", True),
        patch("app.content_pipeline.client") as mock_client,
        patch("app.content_pipeline.asyncio.to_thread", side_effect=Exception("Veo down")),
    ):
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_audio_response(),   # TTS (runs in parallel with Veo attempt)
            mock_image_response(),   # image fallback after Veo fails
        ])
        assets = await generate_scene(decision, scene)
    assert assets.video_base64 is None
    assert assets.image_base64 == "base64imagedata"
    assert assets.audio_base64 == "base64audiodata"


# ---------------------------------------------------------------------------
# VEO_ENABLED=false tests (default dev mode)
# ---------------------------------------------------------------------------

async def test_generate_scene_veo_disabled_returns_image():
    """With VEO_ENABLED=false (default), video_base64 is None, image_base64 is set."""
    scene = make_scene()
    decision = make_decision()
    with (
        patch("app.content_pipeline._VEO_ENABLED", False),
        patch("app.content_pipeline.client") as mock_client,
    ):
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_audio_response(),   # TTS (runs with Veo no-op)
            mock_image_response(),   # image fallback (since Veo returned None)
        ])
        assets = await generate_scene(decision, scene)
    assert assets.video_base64 is None
    assert assets.image_base64 == "base64imagedata"
    assert assets.audio_base64 == "base64audiodata"


async def test_generate_scene_image_fallback_api_failure():
    """Image API also fails → image_base64 is None (graceful degradation)."""
    scene = make_scene()
    decision = make_decision()

    def side_effect(model, **kwargs):
        if "tts" not in model:  # image model — force failure
            raise Exception("Image API down")
        return mock_audio_response()

    with (
        patch("app.content_pipeline._VEO_ENABLED", False),
        patch("app.content_pipeline.client") as mock_client,
    ):
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

    with (
        patch("app.content_pipeline._VEO_ENABLED", False),
        patch("app.content_pipeline.client") as mock_client,
    ):
        mock_client.aio.models.generate_content = AsyncMock(side_effect=side_effect)
        assets = await generate_scene(decision, scene)
    assert assets.image_base64 == "base64imagedata"
    assert assets.audio_base64 is None


async def test_generate_scene_cache_hit():
    scene = make_scene()
    decision = make_decision()
    with (
        patch("app.content_pipeline._VEO_ENABLED", False),
        patch("app.content_pipeline.client") as mock_client,
    ):
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_audio_response(),
            mock_image_response(),
        ])
        first = await generate_scene(decision, scene)
        second = await generate_scene(decision, scene)
    # Only 2 API calls total (TTS + image fallback) for first call; second is cached
    assert mock_client.aio.models.generate_content.call_count == 2
    assert first is second


async def test_generate_scene_parallel():
    scene = make_scene()
    decision = make_decision()
    with (
        patch("app.content_pipeline._VEO_ENABLED", False),
        patch("app.content_pipeline.client") as mock_client,
    ):
        mock_client.aio.models.generate_content = AsyncMock(side_effect=[
            mock_audio_response(),
            mock_image_response(),
        ])
        assets = await generate_scene(decision, scene)
    # asyncio.gather fires TTS + Veo(no-op) in parallel; image fallback fires after
    assert assets.image_base64 is not None
    assert assets.audio_base64 is not None
