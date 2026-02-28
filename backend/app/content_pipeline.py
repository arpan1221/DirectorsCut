import asyncio
import base64
import io
import logging
import wave

from google import genai
from google.genai import types

from app.models import SceneAssets, SceneData, SceneDecision

logger = logging.getLogger(__name__)

client = genai.Client()

_cache: dict[str, SceneAssets] = {}


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """Wrap raw L16 PCM bytes in a WAV container the browser can decode."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)   # mono
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def clear_cache() -> None:
    """Clear the scene cache. Call on story reset so replays regenerate assets."""
    _cache.clear()


async def generate_scene(decision: SceneDecision, scene: SceneData) -> SceneAssets:
    # Composite key so different mood_shifts produce different cached assets
    cache_key = f"{scene.id}__{decision.mood_shift or ''}__{decision.override_narration or ''}"
    if cache_key in _cache:
        return _cache[cache_key]

    async def gen_image() -> str | None:
        try:
            prompt = scene.image_prompt
            if decision.mood_shift:
                prompt = f"{prompt}\nMood: {decision.mood_shift}"
            # Use async client so image + audio run truly in parallel via asyncio.gather
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-05-20",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["image"],
                ),
            )
            raw = response.candidates[0].content.parts[0].inline_data.data
            if isinstance(raw, bytes):
                return base64.b64encode(raw).decode()
            return raw
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None

    async def gen_audio() -> str | None:
        try:
            narration_text = decision.override_narration or scene.narration
            # Use async client so image + audio run truly in parallel via asyncio.gather
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=narration_text,
                config=types.GenerateContentConfig(
                    response_modalities=["audio"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Charon"
                            )
                        )
                    ),
                ),
            )
            raw = response.candidates[0].content.parts[0].inline_data.data
            if isinstance(raw, bytes):
                # Gemini TTS returns raw L16 PCM — wrap in WAV so the browser can decode it
                return base64.b64encode(_pcm_to_wav(raw)).decode()
            return raw
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

    # True parallel generation now that both inner functions are properly async
    image_b64, audio_b64 = await asyncio.gather(gen_image(), gen_audio())

    assets = SceneAssets(
        scene_id=scene.id,
        image_base64=image_b64,
        audio_base64=audio_b64,
        narration_text=decision.override_narration or scene.narration,
        mood=decision.mood_shift or "neutral",
        chapter=scene.chapter,
        duration_seconds=scene.duration_seconds,
    )
    _cache[cache_key] = assets
    return assets
