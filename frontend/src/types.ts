export type EmotionType =
  | 'engaged'
  | 'bored'
  | 'confused'
  | 'amused'
  | 'tense'
  | 'surprised'
  | 'neutral'

export type AttentionType = 'screen' | 'away' | 'uncertain'

export interface EmotionReading {
  primary_emotion: EmotionType
  intensity: number // 1–10
  attention: AttentionType
  confidence: number // 0–1
  timestamp?: string
}

export interface SceneData {
  id: string
  chapter: string
  image_prompt: string
  narration: string
  duration_seconds: number
  next: string | null
  is_decision_point: boolean
  adaptation_rules: Record<string, string> | null
}

export interface SceneAssets {
  scene_id: string
  image_base64: string | null
  audio_base64: string | null
  narration_text: string
  mood: string
  chapter: string
  duration_seconds: number
}

export type AppState = 'idle' | 'calibrating' | 'playing' | 'deciding' | 'ended'

// Messages received from backend WebSocket
export type BackendMessage =
  | { type: 'scene'; assets: SceneAssets }
  | { type: 'emotion'; data: EmotionReading }
  | { type: 'deciding' }
  | { type: 'complete'; ending: string; scenes_played: string[] }
  | { type: 'error'; message: string }
