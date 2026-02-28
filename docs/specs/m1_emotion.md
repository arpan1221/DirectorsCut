# M1: Emotion Service

## Purpose
Takes a webcam frame (base64 JPEG), sends to Gemini 3 Flash for facial expression analysis, returns structured EmotionReading. Also maintains an EmotionAccumulator for smoothing.

## File
`backend/app/emotion_service.py`

## analyze_frame(frame_base64: str) -> EmotionReading

### Gemini Call
- Model: `gemini-3-flash`
- Input: the image as base64 with this prompt:
```
Analyze this webcam image of a person watching a film.
Return ONLY a JSON object with these exact fields:
{
  "primary_emotion": one of "engaged","bored","confused","amused","tense","surprised","neutral",
  "intensity": integer 1-10,
  "attention": one of "screen","away","uncertain",
  "confidence": float 0.0-1.0
}
No other text. Only the JSON object.
```
- Settings: media_resolution=low, thinking_level=none, temperature=0.3
- Parse the JSON response into an EmotionReading (Pydantic model)

### SDK Usage
Use google-genai SDK:
```python
from google import genai
from google.genai import types

client = genai.Client()
response = client.models.generate_content(
    model="gemini-3-flash",
    contents=[
        types.Part.from_bytes(data=base64.b64decode(frame_base64), mime_type="image/jpeg"),
        "Analyze this webcam image..."
    ],
    config=types.GenerateContentConfig(temperature=0.3)
)
```

### Error handling
- If Gemini returns invalid JSON → return EmotionReading with primary_emotion="neutral", intensity=5, attention="uncertain", confidence=0.0
- If API call fails (timeout, rate limit, any exception) → same fallback
- Log all errors but never crash

## EmotionAccumulator class

### State
- `history: list[EmotionReading]` — rolling window, max 8 entries
- `baseline: EmotionReading | None` — set from first frame (calibration)

### Methods
- `add_reading(reading: EmotionReading)` — append, trim to 8
- `get_summary() -> EmotionSummary`:
  - `dominant_emotion`: mode of primary_emotions in window
  - `trend`: compare avg intensity of last 3 vs first 3 — "rising"/"falling"/"stable" (threshold: ±1.5)
  - `intensity_avg`: mean of intensities
  - `attention_score`: fraction with attention=="screen"
  - `volatility`: std dev of intensities
  - `reading_count`: len(history)
- `should_trigger() -> bool`:
  - True if 3+ consecutive same emotion
  - OR intensity spike >4 from baseline
  - OR attention_score < 0.5
  - OR reading_count >= 3 (minimum data)
  - False if reading_count < 3

## Tests to Write (backend/tests/test_emotion.py)
- test_analyze_frame_returns_emotion_reading — mock client, verify EmotionReading fields
- test_analyze_frame_fallback_on_invalid_json — mock returns garbled text, verify neutral fallback
- test_analyze_frame_fallback_on_api_exception — mock raises exception, verify neutral fallback
- test_accumulator_add_reading — add readings, verify history length capped at 8
- test_accumulator_get_summary_dominant — add 5 "engaged" + 2 "bored", dominant is "engaged"
- test_accumulator_should_trigger_consecutive — 3 same emotions → True
- test_accumulator_should_trigger_min_count — only 2 readings → False
