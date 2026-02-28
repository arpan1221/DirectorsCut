# M2: Director Agent

## Purpose
The creative brain. Takes EmotionSummary + StoryState, decides which scene to play next at decision points. Uses Gemini 3 Pro for reasoning.

## File
`backend/app/director_agent.py`

## decide(emotion_summary: EmotionSummary, story_state: StoryState, story_data: dict) -> SceneDecision

### Logic
1. Get current scene from story_state.current_scene_id
2. Find the next node (scene.next)
3. If next node is NOT a decision point → return SceneDecision(next_scene_id=next.id) directly, no Gemini call needed
4. If next node IS a decision point:
   a. Get adaptation_rules from the decision point
   b. Map emotion_summary.dominant_emotion to a branch via adaptation_rules
   c. If no match → use "default" key
   d. Call Gemini 3 Pro with context for creative reasoning about the choice

### Gemini Call (only at decision points)
- Model: `gemini-3-pro-preview`
- Temperature: 0.8
- thinking_level: medium

System prompt:
```
You are the Director of an adaptive mystery film called "The Inheritance".
You are making a narrative decision based on the viewer's emotional state.

Story so far: {scenes_played as brief summary}
Current viewer state: {emotion_summary as JSON}
Available branches: {adaptation_rules as JSON}
Emotion-mapped branch: {pre_selected_branch}

Confirm or override the branch selection. Return ONLY JSON:
{
  "next_scene_id": "the scene id you choose",
  "mood_shift": "tense" or "warm" or "mysterious" or null,
  "pacing": "slow" or "medium" or "fast",
  "reasoning": "One sentence explaining your choice"
}
```

### Error handling
- If Gemini call fails → use the simple mapping (dominant_emotion → adaptation_rules) without reasoning
- If mapped scene doesn't exist → use "default" branch
- Never crash, always return a valid SceneDecision

### Important
- Do NOT call Gemini Pro for non-decision-point transitions. Just return the next scene directly.
- Each Gemini Pro call costs ~$0.005. Budget allows ~40 total calls. Only 3-4 per demo run.

## Tests to Write (backend/tests/test_director.py)
- test_decide_non_decision_point — next scene is normal, no Gemini call, returns SceneDecision directly
- test_decide_at_decision_point_calls_gemini — mock Gemini Pro, verify SceneDecision returned with reasoning
- test_decide_fallback_on_gemini_failure — Gemini raises exception, fallback to emotion mapping
- test_decide_uses_default_when_no_emotion_match — emotion not in adaptation_rules, uses "default"
