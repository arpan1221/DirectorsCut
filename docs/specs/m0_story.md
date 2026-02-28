# M0: Story Engine

## Purpose
Loads story.json, manages story state, provides graph traversal.

## File
`backend/app/story_engine.py`

## Input/Output
- `load_story(path: str) -> dict` — load and validate story.json
- `get_scene(scene_id: str, story_data: dict) -> SceneData` — return a scene by ID
- `get_branches(scene: SceneData) -> dict[str, str]` — return adaptation_rules for a decision point
- `advance(story_state: StoryState, next_scene_id: str) -> StoryState` — update state

## StoryState (from models.py)
Tracks: current_scene_id, scenes_played list, current_chapter, genre

## story.json format
```json
{
  "title": "The Inheritance",
  "genre": "mystery",
  "scenes": {
    "scene_id": {
      "id": "scene_id",
      "chapter": "Chapter Name",
      "image_prompt": "Cinematic film still...",
      "narration": "The narrator says...",
      "duration_seconds": 16,
      "next": "next_scene_id or null",
      "is_decision_point": false,
      "adaptation_rules": null
    }
  }
}
```

For decision points: `is_decision_point: true`, `next: null`, and `adaptation_rules` maps emotion states to scene IDs:
```json
{
  "adaptation_rules": {
    "engaged": "scene_a",
    "tense": "scene_a",
    "bored": "scene_b",
    "neutral": "scene_b",
    "confused": "scene_c",
    "default": "scene_a"
  }
}
```

## Error Handling
- Missing scene_id → raise ValueError with descriptive message
- Invalid story.json → raise on startup, don't silently fail
- Non-decision-point scene accessed for branches → raise ValueError

## Tests to Write (backend/tests/test_story.py)
- test_load_story_returns_dict — load story.json, verify it has "scenes" key
- test_get_scene_valid_id — get "opening" scene, verify SceneData fields
- test_get_scene_invalid_id — raises ValueError
- test_get_branches_decision_point — get decision_1 branches, verify dict
- test_get_branches_non_decision_point — raises ValueError
- test_advance_state — verify scenes_played grows, current_scene_id updates
