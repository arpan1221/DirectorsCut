Build the frontend as a single index.html file.

Process:
1. Read docs/specs/m4_frontend.md completely
2. Read CLAUDE.md for the layout spec
3. Create frontend/index.html with inline CSS and JS (no build step, no npm)
4. Implement:
   - Webcam capture with getUserMedia
   - Scene image display with CSS crossfade transitions (opacity 0.8s ease)
   - Audio playback element
   - Emotion indicator (emoji + label + intensity bar)
   - Story metadata display (chapter, scene count, mood)
   - WebSocket connection to ws://localhost:8000/ws/session
   - Start/Reset buttons
   - Genre selector (pre-filled with "mystery")
   - Calibration countdown (3 seconds)
   - End screen showing "Your Film DNA": scenes played, which ending
5. Style it dark and cinematic — black background, minimal UI, let the scene image dominate
6. Test by opening in browser with backend running (uvicorn must be running)
