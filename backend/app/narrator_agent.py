import logging
import os

from llama_index.llms.google_genai import GoogleGenAI

from app.models import EmotionSummary

logger = logging.getLogger(__name__)

# Lazy singleton — created after load_dotenv() has run
_llm: GoogleGenAI | None = None


def _get_llm() -> GoogleGenAI:
    global _llm
    if _llm is None:
        _llm = GoogleGenAI(
            model="gemini-2.5-flash",
            api_key=os.environ.get("GOOGLE_API_KEY", ""),
            temperature=0.8,
        )
    return _llm


async def adapt_narration(
    seed: str,
    mood: str | None,
    pacing: str,
    emotion: EmotionSummary,
    scenes_played: list[str],
) -> str:
    """
    Rewrite the seed narration to match this viewer's specific emotional state.
    Falls back to the original seed on any failure — never crashes.
    """
    if not seed.strip():
        return seed

    prompt = f"""You are the narrator of an adaptive mystery film called "The Inheritance".
Rewrite this narration line to match a specific viewer's emotional state right now.

Original narration: "{seed}"
Viewer: {emotion.dominant_emotion.value} emotion, intensity {emotion.intensity_avg:.1f}/10, trend: {emotion.trend}
Director's intent: mood={mood or 'neutral'}, pacing={pacing}
Scene number: {len(scenes_played) + 1}

Adaptation rules — apply the one that matches the viewer:
- BORED or falling intensity → urgency, shorter sentences, active verbs, lean forward
- TENSE or rising intensity → one small breath of relief, then push forward
- CONFUSED → add a single grounding phrase, slow the rhythm
- ENGAGED or AMUSED → deepen the atmosphere, lean into the mood, trust the viewer
- All other states → serve the director's mood and pacing intent

Return ONLY the adapted narration text (1-3 sentences).
No quotes. No labels. No explanation. Just the narration."""

    try:
        llm = _get_llm()
        response = await llm.acomplete(prompt)
        adapted = response.text.strip().strip('"').strip("'")
        return adapted if adapted else seed
    except Exception as e:
        logger.error(f"Narrator agent failed: {e}")
        return seed  # always fall back to original
