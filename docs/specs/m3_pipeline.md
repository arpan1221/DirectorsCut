# M3: Content Pipeline

## Purpose
Takes a SceneDecision + SceneData, generates the scene image and narration audio in parallel. Returns SceneAssets.

## File
`backend/app/content_pipeline.py`

## generate_scene(decision: SceneDecision, scene: SceneData) -> SceneAssets

### Image Generation
- Model: `gemini-2.5-flash-image`
- Prompt: scene.image_prompt (already includes style direction)
  - If decision.mood_shift is set, append: "Mood: {mood_shift}"
- Output: base64 encoded image string
- Extract from response: `response.candidates[0].content.parts[0].inline_data.data`

### TTS Narration
- Model: `gemini-2.5-flash-preview-tts`
- Input text: decision.override_narration or scene.narration
- Voice: pick a deep, dramatic male voice for mystery genre (e.g., "Charon")
- Output: base64 encoded audio
- Extract from response: `response.candidates[0].content.parts[0].inline_data.data`

### SDK Usage
```python
from google import genai
from google.genai import types

client = genai.Client()

# Image
img_response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["image"]
    )
)

# TTS
tts_response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=narration_text,
    config=types.GenerateContentConfig(
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
            )
        )
    )
)
```

### Parallel execution
- Use asyncio.gather to run image gen and TTS concurrently
- Both are independent — if one fails, still return the other
- Wrap each in its own try/except before gather

### Caching
- Maintain a module-level dict[str, SceneAssets] keyed by scene_id
- Before generating, check cache. If hit, return cached version.
- This prevents re-generating the same scene and saves ~$0.04 per cache hit.

### Error handling
- Image gen fails → return SceneAssets with image_base64=None (frontend shows narration-only)
- TTS fails → return SceneAssets with audio_base64=None (frontend shows text subtitle only)
- Both fail → return SceneAssets with just narration_text (degraded but functional)
- Log all errors, never crash

### Cost control
- ALWAYS use gemini-2.5-flash-image, NEVER gemini-3-pro-image-preview
- Check cache before every generation

## Tests to Write (backend/tests/test_pipeline.py)
- test_generate_scene_returns_assets — mock both API calls, verify SceneAssets fields
- test_generate_scene_image_fallback — image API raises, verify image_base64=None but audio present
- test_generate_scene_tts_fallback — TTS API raises, verify audio_base64=None but image present
- test_generate_scene_cache_hit — call generate twice for same scene_id, second call skips API
- test_generate_scene_parallel — verify asyncio.gather used (both calls fire simultaneously)
