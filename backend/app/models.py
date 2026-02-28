from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class EmotionType(str, Enum):
    ENGAGED = "engaged"
    BORED = "bored"
    CONFUSED = "confused"
    AMUSED = "amused"
    TENSE = "tense"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"


class AttentionType(str, Enum):
    SCREEN = "screen"
    AWAY = "away"
    UNCERTAIN = "uncertain"


class Pacing(str, Enum):
    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"


class EmotionReading(BaseModel):
    primary_emotion: EmotionType
    intensity: int = Field(ge=1, le=10)
    attention: AttentionType
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)


class EmotionSummary(BaseModel):
    dominant_emotion: EmotionType
    trend: str  # "rising", "falling", "stable"
    intensity_avg: float
    attention_score: float
    volatility: float
    reading_count: int


class SceneData(BaseModel):
    id: str
    chapter: str = ""
    image_prompt: str = ""
    narration: str = ""
    duration_seconds: int = 16
    next: str | None = None
    is_decision_point: bool = False
    adaptation_rules: dict[str, str] | None = None


class SceneDecision(BaseModel):
    next_scene_id: str
    override_narration: str | None = None
    mood_shift: str | None = None
    pacing: Pacing = Pacing.MEDIUM
    reasoning: str = ""


class SceneAssets(BaseModel):
    scene_id: str
    image_base64: str | None = None
    audio_base64: str | None = None
    narration_text: str
    mood: str
    chapter: str
    duration_seconds: int = 16


class StoryState(BaseModel):
    current_scene_id: str = "opening"
    scenes_played: list[str] = []
    current_chapter: str = "The Arrival"
    genre: str = "mystery"


class FrameInput(BaseModel):
    image_base64: str


class SessionMessage(BaseModel):
    type: str  # "frame", "start", "reset"
    data: str | None = None
    genre: str | None = None
