from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.emotion_service import EmotionAccumulator, analyze_frame
from app.models import AttentionType, EmotionReading, EmotionType


async def test_analyze_frame_returns_emotion_reading(mock_gemini_emotion_response, fake_frame_base64):
    with patch("app.emotion_service.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_gemini_emotion_response)
        reading = await analyze_frame(fake_frame_base64)
    assert isinstance(reading, EmotionReading)
    assert reading.primary_emotion == EmotionType.ENGAGED
    assert reading.intensity == 7
    assert reading.attention == AttentionType.SCREEN


async def test_analyze_frame_fallback_on_invalid_json(fake_frame_base64):
    mock_resp = MagicMock()
    mock_resp.text = "not valid json at all {{{"
    with patch("app.emotion_service.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)
        reading = await analyze_frame(fake_frame_base64)
    assert reading.primary_emotion == EmotionType.NEUTRAL
    assert reading.confidence == 0.0


async def test_analyze_frame_fallback_on_api_exception(fake_frame_base64):
    with patch("app.emotion_service.client") as mock_client:
        mock_client.aio.models.generate_content = AsyncMock(side_effect=Exception("API error"))
        reading = await analyze_frame(fake_frame_base64)
    assert reading.primary_emotion == EmotionType.NEUTRAL
    assert reading.confidence == 0.0


def test_accumulator_add_reading():
    acc = EmotionAccumulator()
    for i in range(10):
        acc.add_reading(EmotionReading(
            primary_emotion=EmotionType.ENGAGED, intensity=7,
            attention=AttentionType.SCREEN, confidence=0.9
        ))
    assert len(acc.history) == 8  # capped at 8


def test_accumulator_get_summary_dominant():
    acc = EmotionAccumulator()
    for _ in range(5):
        acc.add_reading(EmotionReading(
            primary_emotion=EmotionType.ENGAGED, intensity=7,
            attention=AttentionType.SCREEN, confidence=0.9
        ))
    for _ in range(2):
        acc.add_reading(EmotionReading(
            primary_emotion=EmotionType.BORED, intensity=3,
            attention=AttentionType.AWAY, confidence=0.6
        ))
    summary = acc.get_summary()
    assert summary.dominant_emotion == EmotionType.ENGAGED


def test_accumulator_should_trigger_consecutive():
    acc = EmotionAccumulator()
    for _ in range(3):
        acc.add_reading(EmotionReading(
            primary_emotion=EmotionType.TENSE, intensity=8,
            attention=AttentionType.SCREEN, confidence=0.9
        ))
    assert acc.should_trigger() is True


def test_accumulator_should_trigger_min_count():
    acc = EmotionAccumulator()
    for _ in range(2):
        acc.add_reading(EmotionReading(
            primary_emotion=EmotionType.ENGAGED, intensity=7,
            attention=AttentionType.SCREEN, confidence=0.9
        ))
    assert acc.should_trigger() is False
