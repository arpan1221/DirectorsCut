# M4: Frontend

## Purpose
Single-page app. Displays the film experience: scene image, narration audio, webcam preview, emotion indicator, story metadata. Communicates with backend via REST + WebSocket.

## File
`frontend/index.html` — single file with inline CSS and JS (no build step, no npm)

## Layout
```
┌───────────────────────────────────────────────────┐
│  DIRECTOR'S CUT          [Genre: Mystery]          │
├───────────────────────────────────────────────────┤
│                                    ┌─────────────┐│
│                                    │ 📷 Webcam   ││
│   ┌──────────────────────────┐     │  (200x150)  ││
│   │                          │     ├─────────────┤│
│   │    SCENE IMAGE           │     │ 😊 Engaged  ││
│   │    (fills main area)     │     │ Intensity: 7││
│   │                          │     │ ████████░░  ││
│   └──────────────────────────┘     └─────────────┘│
│                                                    │
│   "The door creaked open, revealing a room..."     │
│                                                    │
│   Ch: The Arrival  |  Scene 3/12  |  🎭 Mysterious│
├───────────────────────────────────────────────────┤
│  [ ▶ Start ]  [ 🎬 Pick Genre ]  [ ⟳ Reset ]     │
└───────────────────────────────────────────────────┘
```

## Webcam
- Use navigator.mediaDevices.getUserMedia({video: true})
- Small preview element top-right (200x150)
- Every 8 seconds: capture frame to canvas → toDataURL('image/jpeg', 0.7) → strip prefix → send to backend

## Scene Display
- Image: <img> element with CSS transition: opacity 0.8s ease
- Swap by setting new src, toggling opacity for crossfade
- Audio: <audio> element with autoplay
- Subtitle: narration text displayed below image

## WebSocket Flow (preferred)
```
Client connects to ws://localhost:8000/ws/session
Client sends: { "type": "frame", "data": "base64..." } every 8s
Server sends: { "type": "scene", "assets": SceneAssets } when new scene ready
Server sends: { "type": "emotion", "data": EmotionReading } after each frame analysis
Client sends: { "type": "start", "genre": "mystery" } to begin
Client sends: { "type": "reset" } to restart
```

## Fallback (REST polling if WS is buggy)
- POST /api/emotion every 8s with frame
- GET /api/story/state to check if scene changed

## States
1. **IDLE**: title screen, genre picker, camera permission prompt
2. **CALIBRATING**: 3-second countdown, captures baseline emotion
3. **PLAYING**: film running, scenes auto-advancing
4. **DECIDING**: brief "Director is thinking..." overlay at decision points
5. **ENDED**: show "Your Film DNA" — list of scenes played, ending reached, emotion chart

## Error states
- Camera denied → show notice, run linear story (no adaptation)
- WebSocket disconnect → fall back to REST polling
- Scene image missing → show dark background with narration text only

## Styling
- Dark cinematic theme: black background, white text
- Scene image fills 70% of viewport
- Minimal UI — let the image dominate
- Emotion indicator: emoji + label + intensity bar (CSS)
- CSS transitions for image crossfade (opacity 0.8s ease)
- No external CSS frameworks — all inline
