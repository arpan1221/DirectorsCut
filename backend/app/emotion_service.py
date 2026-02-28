import base64
import json
import logging
import statistics

from google import genai
from google.genai import types

from app.models import AttentionType, EmotionReading, EmotionSummary, EmotionType

logger = logging.getLogger(__name__)

client = genai.Client()

_EMOTION_PROMPT = """Analyze this webcam image of a person watching a film.
Return ONLY a JSON object with these exact fields:
{
  "primary_emotion": one of "engaged","bored","confused","amused","tense","surprised","neutral",
  "intensity": integer 1-10,
  "attention": one of "screen","away","uncertain",
  "confidence": float 0.0-1.0
}
No other text. Only the JSON object."""

_FALLBACK = {
    "primary_emotion": "neutral",
    "intensity": 5,
    "attention": "uncertain",
    "confidence": 0.0,
}


async def analyze_frame(frame_base64: str) -> EmotionReading:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(
                    data=base64.b64decode(frame_base64),
                    mime_type="image/jpeg",
                ),
                _EMOTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        # Strip markdown fences if model wraps JSON in ```json ... ```
        raw = (response.text or "").strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(raw)
        return EmotionReading(**data)
    except Exception as e:
        logger.error(f"analyze_frame failed: {e}")
        return EmotionReading(**_FALLBACK)


class EmotionAccumulator:
    def __init__(self) -> None:
        self.history: list[EmotionReading] = []
        self.baseline: EmotionReading | None = None

    def add_reading(self, reading: EmotionReading) -> None:
        if self.baseline is None:
            self.baseline = reading
        self.history.append(reading)
        if len(self.history) > 8:
            self.history = self.history[-8:]

    def get_summary(self) -> EmotionSummary:
        if not self.history:
            return EmotionSummary(
                dominant_emotion=EmotionType.NEUTRAL,
                trend="stable",
                intensity_avg=5.0,
                attention_score=0.0,
                volatility=0.0,
                reading_count=0,
            )

        emotions = [r.primary_emotion for r in self.history]
        dominant = max(set(emotions), key=emotions.count)

        intensities = [r.intensity for r in self.history]
        intensity_avg = sum(intensities) / len(intensities)

        if len(self.history) >= 6:
            first_avg = sum(intensities[:3]) / 3
            last_avg = sum(intensities[-3:]) / 3
            delta = last_avg - first_avg
            if delta > 1.5:
                trend = "rising"
            elif delta < -1.5:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"

        attention_score = (
            sum(1 for r in self.history if r.attention == AttentionType.SCREEN)
            / len(self.history)
        )
        volatility = statistics.stdev(intensities) if len(intensities) > 1 else 0.0

        return EmotionSummary(
            dominant_emotion=dominant,
            trend=trend,
            intensity_avg=intensity_avg,
            attention_score=attention_score,
            volatility=volatility,
            reading_count=len(self.history),
        )

    def should_trigger(self) -> bool:
        if len(self.history) < 3:
            return False

        # 3+ consecutive same emotion
        last_three = [r.primary_emotion for r in self.history[-3:]]
        if len(set(last_three)) == 1:
            return True

        # intensity spike >4 from baseline
        if self.baseline is not None:
            for r in self.history[-3:]:
                if abs(r.intensity - self.baseline.intensity) > 4:
                    return True

        # attention_score < 0.5
        summary = self.get_summary()
        if summary.attention_score < 0.5:
            return True

        # reading_count >= 3 (minimum data threshold reached)
        return True
