import asyncio
import base64
import logging

from google import genai
from google.genai import types

from app.models import SceneAssets, SceneData, SceneDecision

logger = logging.getLogger(__name__)

client = genai.Client()

_cache: dict[str, SceneAssets] = {}


async def generate_scene(decision: SceneDecision, scene: SceneData) -> SceneAssets:
    if scene.id in _cache:
        return _cache[scene.id]

    async def gen_image() -> str | None:
        try:
            prompt = scene.image_prompt
            if decision.mood_shift:
                prompt = f"{prompt}\nMood: {decision.mood_shift}"
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
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
            response = client.models.generate_content(
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
                return base64.b64encode(raw).decode()
            return raw
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return None

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
    _cache[scene.id] = assets
    return assets
