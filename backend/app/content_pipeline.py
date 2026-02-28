import asyncio
import base64
import io
import logging
import os
import wave

from google import genai
from google.genai import types

from app.models import SceneAssets, SceneData, SceneDecision

logger = logging.getLogger(__name__)

client = genai.Client()

_cache: dict[str, SceneAssets] = {}

# Set VEO_ENABLED=true in .env to use real Veo video generation.
# Default is false so dev/test runs never burn video credits.
_VEO_ENABLED: bool = os.getenv("VEO_ENABLED", "false").lower() == "true"

_VEO_MODEL = "veo-3.0-generate-001"
_VEO_DURATION_SECONDS = 6       # cheapest supported duration (4, 6, or 8)
_VEO_POLL_INTERVAL = 8          # seconds between polling attempts
_VEO_TIMEOUT_SECONDS = 90       # give up and fall back to image after this

_GENRE_VISUAL_STYLE: dict[str, str] = {
    "mystery":  "",  # original prompts already target mystery
    "thriller": "high contrast, desaturated palette, claustrophobic framing, cold institutional lighting, extreme tension",
    "horror":   "deep shadows, off-kilter dutch angle, pale sickly moonlight, unsettling negative space, cold blue-grey horror palette",
    "sci-fi":   "retrofuturism, cool neon-and-silver accents, holographic surface details, technological decay woven into Victorian architecture, blue-white lighting",
}


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


def _build_visual_prompt(scene: SceneData, genre: str, decision: SceneDecision) -> str:
    """Compose the final visual prompt from scene data, genre style, and mood."""
    prompt = scene.image_prompt.replace("mystery genre", f"{genre} genre").replace(
        "meets mystery:", f"meets {genre}:"
    )
    style = _GENRE_VISUAL_STYLE.get(genre, "")
    if style:
        prompt = f"{prompt}\nAdditional visual style: {style}"
    if decision.mood_shift:
        prompt = f"{prompt}\nMood: {decision.mood_shift}"
    return prompt


async def generate_scene(
    decision: SceneDecision,
    scene: SceneData,
    genre: str = "mystery",
) -> SceneAssets:
    # Composite key: genre + mood_shift + override_narration ensure no cross-genre cache collisions
    cache_key = f"{scene.id}__{genre}__{decision.mood_shift or ''}__{decision.override_narration or ''}"
    if cache_key in _cache:
        return _cache[cache_key]

    async def gen_video() -> str | None:
        """Generate a short MP4 clip via Veo. Returns base64-encoded bytes or None."""
        if not _VEO_ENABLED:
            return None
        try:
            prompt = _build_visual_prompt(scene, genre, decision)
            # Veo uses generate_videos (long-running operation), not generate_content.
            # Wrap in asyncio.to_thread because the SDK call is synchronous.
            operation = await asyncio.to_thread(
                client.models.generate_videos,
                model=_VEO_MODEL,
                prompt=prompt,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    duration_seconds=_VEO_DURATION_SECONDS,
                    resolution="720p",
                ),
            )
            # Poll until operation completes or timeout expires
            loop = asyncio.get_event_loop()
            deadline = loop.time() + _VEO_TIMEOUT_SECONDS
            while not operation.done:
                if loop.time() > deadline:
                    raise TimeoutError(
                        f"Veo timed out after {_VEO_TIMEOUT_SECONDS}s for scene '{scene.id}'"
                    )
                await asyncio.sleep(_VEO_POLL_INTERVAL)
                operation = await asyncio.to_thread(client.operations.get, operation)

            raw_video = operation.response.generated_videos[0].video
            video_bytes: bytes = await asyncio.to_thread(raw_video.fetch)
            return base64.b64encode(video_bytes).decode()
        except Exception as e:
            logger.error(f"Veo generation failed for scene '{scene.id}', will fall back to image: {e}")
            return None

    async def gen_image() -> str | None:
        """Generate a static PNG via Gemini Flash Image. Used as Veo fallback."""
        try:
            prompt = _build_visual_prompt(scene, genre, decision)
            response = await client.aio.models.generate_content(
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
            logger.error(f"Image generation failed for scene '{scene.id}': {e}")
            return None

    async def gen_audio() -> str | None:
        try:
            narration_text = decision.override_narration or scene.narration
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
            logger.error(f"TTS generation failed for scene '{scene.id}': {e}")
            return None

    # Run Veo (or no-op if disabled) and TTS in parallel
    video_b64, audio_b64 = await asyncio.gather(gen_video(), gen_audio())

    # If Veo produced nothing, fall back to static image — never leave a scene blank
    image_b64: str | None = None
    if video_b64 is None:
        image_b64 = await gen_image()

    assets = SceneAssets(
        scene_id=scene.id,
        video_base64=video_b64,
        image_base64=image_b64,
        audio_base64=audio_b64,
        narration_text=decision.override_narration or scene.narration,
        mood=decision.mood_shift or "neutral",
        chapter=scene.chapter,
        duration_seconds=scene.duration_seconds,
    )
    _cache[cache_key] = assets
    return assets
