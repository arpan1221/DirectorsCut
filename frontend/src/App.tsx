import { useCallback, useEffect, useRef, useState } from 'react'
import { useCamera } from './hooks/useCamera'
import { useGeminiLive } from './hooks/useGeminiLive'
import { useBackendWS } from './hooks/useBackendWS'
import { StoryMap } from './StoryMap'
import type { AppState, BackendMessage, EmotionReading, SceneAssets } from './types'

// Vite injects VITE_* vars at build time; undefined in dev without .env.local
const GEMINI_API_KEY = (import.meta.env.VITE_GEMINI_API_KEY as string) ?? ''

const FRAME_INTERVAL_MS = 10_000

const GENRES = ['mystery', 'thriller', 'horror', 'sci-fi']

const GENRE_TITLES: Record<string, string> = {
  mystery:  'The Inheritance',
  thriller: 'The Last Signal',
  horror:   'The Haunting',
  'sci-fi': 'The Inheritance Protocol',
}

const EMOTION_EMOJI: Record<string, string> = {
  engaged: '😊', bored: '😑', confused: '🤔',
  amused: '😄', tense: '😰', surprised: '😲', neutral: '😐',
}
const EMOTION_COLOR: Record<string, string> = {
  engaged: '#2ecc71', bored: '#7f8c8d', confused: '#e67e22',
  amused: '#f1c40f', tense: '#e74c3c', surprised: '#9b59b6', neutral: '#95a5a6',
}
const ENDINGS: Record<string, string> = {
  ending_solve:        'The Truth Revealed',
  ending_bittersweet:  'A Bittersweet Resolution',
  ending_twist:        'Nothing Was As It Seemed',
  ending_humorous:     'The Cat Gets Everything',
  ending_supernatural: 'You Never Left',
}

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [assets, setAssets] = useState<SceneAssets | null>(null)
  const [emotion, setEmotion] = useState<EmotionReading | null>(null)
  const [emotionHistory, setEmotionHistory] = useState<string[]>([])
  const [scenesPlayed, setScenesPlayed] = useState<string[]>([])
  const [ending, setEnding] = useState<string | null>(null)
  const [imgVisible, setImgVisible] = useState(false)
  const [calibCount, setCalibCount] = useState(3)
  const [selectedGenre, setSelectedGenre] = useState<string>('mystery')

  // Keep a stable ref to sendEmotion so the Gemini Live callback doesn't capture stale closures
  const sendEmotionRef = useRef<(r: EmotionReading) => void>(() => {})
  const frameTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Refs to avoid stale closures in callbacks and interval handlers
  const appStateRef = useRef<AppState>('idle')
  const liveConnectedRef = useRef(false)
  const startedRef = useRef(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [audioBlocked, setAudioBlocked] = useState(false)
  // Ending held here until audio finishes; fallback timer fires if audio is blocked
  const pendingEndingRef = useRef<{ ending: string; scenes_played: string[] } | null>(null)
  const endTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Trigger end screen — called from audio onEnded or fallback timer
  const triggerEnded = useCallback(() => {
    const p = pendingEndingRef.current
    if (!p) return
    pendingEndingRef.current = null
    if (endTimerRef.current) { clearTimeout(endTimerRef.current); endTimerRef.current = null }
    setEnding(p.ending)
    setScenesPlayed(p.scenes_played)
    setAppState('ended')
  }, [])

  // ── Gemini Live API callback (called on each emotion reading from Gemini) ──
  const handleEmotion = useCallback((reading: EmotionReading) => {
    setEmotion(reading)
    setEmotionHistory((h) => [...h.slice(-7), reading.primary_emotion])
    sendEmotionRef.current(reading)
  }, [])

  // ── Backend WebSocket message handler ──
  const handleWSMessage = useCallback((msg: BackendMessage) => {
    switch (msg.type) {
      case 'scene':
        setImgVisible(false)
        setTimeout(() => {
          setAssets(msg.assets)
          setScenesPlayed((p) => [...p, msg.assets.scene_id])
          setImgVisible(true)
          // Only transition to playing if the film has been explicitly started
          if (startedRef.current && appStateRef.current !== 'ended') setAppState('playing')
        }, 400)
        break
      case 'emotion':
        setEmotion(msg.data)
        setEmotionHistory((h) => [...h.slice(-7), msg.data.primary_emotion])
        break
      case 'deciding':
        // Director decides silently in the background — film keeps playing, no overlay
        break
      case 'complete':
        // Store the ending; show end screen only after audio finishes (or fallback timer)
        pendingEndingRef.current = { ending: msg.ending, scenes_played: msg.scenes_played }
        // Fallback: scene duration + 4 s grace in case audio is blocked or very short
        if (endTimerRef.current) clearTimeout(endTimerRef.current)
        endTimerRef.current = setTimeout(triggerEnded, ((assets?.duration_seconds ?? 20) + 4) * 1000)
        break
      case 'error':
        console.error('Backend error:', msg.message)
        break
    }
  }, [])

  const { videoRef, canvasRef, startCamera, stopCamera, captureFrame } = useCamera()
  const { connect: liveConnect, disconnect: liveDisconnect, sendFrame: liveSendFrame, connected: liveConnected } =
    useGeminiLive(handleEmotion)
  const { connect: wsConnect, disconnect: wsDisconnect, send: wsSend, sendEmotion, connected: wsConnected } =
    useBackendWS(handleWSMessage)

  // Keep sendEmotionRef current
  useEffect(() => {
    sendEmotionRef.current = sendEmotion
  }, [sendEmotion])

  // Keep refs in sync with state/connected values
  useEffect(() => { appStateRef.current = appState }, [appState])
  useEffect(() => { liveConnectedRef.current = liveConnected }, [liveConnected])

  // Connect to backend WS on mount; clean up frame timer on unmount
  useEffect(() => {
    wsConnect()
    return () => {
      wsDisconnect()
      if (frameTimerRef.current) clearInterval(frameTimerRef.current)
    }
  }, [wsConnect, wsDisconnect])

  // ── Calibration countdown then start ──
  const runCalibration = useCallback(
    (onDone: () => void) => {
      setAppState('calibrating')
      let n = 3
      setCalibCount(n)
      const tick = () => {
        n--
        if (n > 0) {
          setCalibCount(n)
          setTimeout(tick, 1000)
        } else {
          onDone()
        }
      }
      setTimeout(tick, 1000)
    },
    [],
  )

  const startFilm = useCallback(async () => {
    const camOk = await startCamera()
    if (!camOk) console.warn('Camera denied — emotion detection will rely on backend only')

    // Connect Gemini Live API (handles empty key gracefully)
    await liveConnect(GEMINI_API_KEY)

    // Start frame interval — read liveConnectedRef so the closure never goes stale
    frameTimerRef.current = setInterval(() => {
      const frame = captureFrame()
      if (frame) {
        if (liveConnectedRef.current) {
          // Primary: Gemini Live API does emotion detection client-side
          liveSendFrame(frame)
        } else {
          // Fallback: send raw frame to backend for server-side analysis
          wsSend({ type: 'frame', data: frame })
        }
      } else if (!liveConnectedRef.current) {
        // No camera + no Gemini Live: send synthetic neutral reading so the story still advances
        sendEmotionRef.current({
          primary_emotion: 'neutral',
          intensity: 5,
          attention: 'screen',
          confidence: 0.5,
        })
      }
    }, FRAME_INTERVAL_MS)

    startedRef.current = true
    wsSend({ type: 'start', genre: selectedGenre })
    setAppState('playing')
  }, [startCamera, liveConnect, captureFrame, liveSendFrame, wsSend, selectedGenre])

  const handleStart = useCallback(() => {
    runCalibration(startFilm)
  }, [runCalibration, startFilm])

  const handleReset = useCallback(() => {
    if (frameTimerRef.current) { clearInterval(frameTimerRef.current); frameTimerRef.current = null }
    if (endTimerRef.current) { clearTimeout(endTimerRef.current); endTimerRef.current = null }
    pendingEndingRef.current = null
    startedRef.current = false
    liveDisconnect()
    stopCamera()
    setAppState('idle')
    setAssets(null)
    setEmotion(null)
    setEmotionHistory([])
    setScenesPlayed([])
    setEnding(null)
    setImgVisible(false)
    setAudioBlocked(false)
    wsSend({ type: 'reset' })
  }, [liveDisconnect, stopCamera, wsSend])

  return (
    <div className="app">
      {/* ── HEADER ── */}
      <header className="header">
        <div className="header-left">
          <div className="sprocket">
            <div className="sprocket-hole" /><div className="sprocket-hole" /><div className="sprocket-hole" />
          </div>
          <h1 className="title"><span>Director's</span> Cut</h1>
          <div className="sprocket">
            <div className="sprocket-hole" /><div className="sprocket-hole" /><div className="sprocket-hole" />
          </div>
        </div>
        <div className="header-right">
          <span>Genre:</span>
          <span className="genre-label">{selectedGenre.charAt(0).toUpperCase() + selectedGenre.slice(1)}</span>
          <div className="header-sep" />
          {appState === 'playing' && <div className="rec-indicator"><div className="rec-dot" /><span>REC</span></div>}
        </div>
      </header>

      {/* ── MAIN CONTENT ── */}
      <main className="content">
        {/* Scene panel */}
        <section className="scene-panel">
          {/* Idle overlay */}
          {appState === 'idle' && (
            <div className="scene-overlay idle-overlay">
              <div className="idle-aperture" />
              <p className="idle-text">{GENRE_TITLES[selectedGenre] ?? 'The Inheritance'}</p>
              <p className="idle-sub">An Adaptive {selectedGenre.charAt(0).toUpperCase() + selectedGenre.slice(1)} Film</p>
            </div>
          )}

          {/* Calibration countdown */}
          {appState === 'calibrating' && (
            <div className="scene-overlay calibrate-overlay">
              <div className="calibrate-count">{calibCount}</div>
              <div className="calibrate-label">Get in frame…</div>
            </div>
          )}

          {assets?.video_base64 ? (
            // Veo video: muted so autoplay is allowed; TTS narration audio plays separately
            <video
              key={assets.scene_id}
              className={`scene-img ${imgVisible ? 'visible' : ''}`}
              src={`data:video/mp4;base64,${assets.video_base64}`}
              autoPlay
              muted
              playsInline
              loop
              style={{ '--scene-dur': `${assets.duration_seconds ?? 20}s` } as React.CSSProperties}
            />
          ) : assets?.image_base64 ? (
            // Static image fallback (Veo disabled or timed out)
            <img
              key={assets.scene_id}
              className={`scene-img ${imgVisible ? 'visible' : ''}`}
              src={`data:image/png;base64,${assets.image_base64}`}
              alt="Scene"
              style={{ '--scene-dur': `${assets.duration_seconds ?? 20}s` } as React.CSSProperties}
            />
          ) : null}
          <div className="vignette" />
        </section>

        {/* Sidebar */}
        <aside className="sidebar">
          {/* Camera feed */}
          <div className="sidebar-section">
            <div className="section-label">Viewer Feed</div>
            <div className="webcam-wrap">
              <video ref={videoRef} className="webcam" autoPlay muted playsInline />
              <div className="crosshair">
                <div className="ch-corner ch-tl" /><div className="ch-corner ch-tr" />
                <div className="ch-corner ch-bl" /><div className="ch-corner ch-br" />
                <div className="crosshair-center" />
              </div>
            </div>
          </div>

          {/* Emotion */}
          <div className="sidebar-section emotion-section">
            <div className="section-label">Emotional Reading</div>
            <div className="emotion-display">
              <span
                className="emotion-emoji"
                style={{ transform: emotion ? 'scale(1)' : undefined }}
              >
                {emotion ? (EMOTION_EMOJI[emotion.primary_emotion] ?? '😐') : '😐'}
              </span>
              <div className="emotion-info">
                <div
                  className="emotion-label"
                  style={{ color: emotion ? EMOTION_COLOR[emotion.primary_emotion] : undefined }}
                >
                  {emotion ? emotion.primary_emotion.charAt(0).toUpperCase() + emotion.primary_emotion.slice(1) : 'Neutral'}
                </div>
                <div className="emotion-meta">
                  {emotion ? `Confidence ${Math.round(emotion.confidence * 100)}%` : 'Awaiting data'}
                </div>
              </div>
            </div>

            {/* Intensity bar */}
            <div className="intensity-wrap">
              <div className="intensity-label">
                <span>Intensity</span>
                <span>{emotion?.intensity ?? 5}/10</span>
              </div>
              <div className="intensity-track">
                <div
                  className="intensity-fill"
                  style={{ width: `${((emotion?.intensity ?? 5) / 10) * 100}%` }}
                />
              </div>
            </div>

            {/* Metrics */}
            <div className="metrics-row">
              <div className="metric-pill">
                <span className="metric-val">{emotion?.attention ?? '—'}</span>
                <span className="metric-key">Attention</span>
              </div>
              <div className="metric-pill">
                <span className="metric-val">
                  {liveConnected ? 'Live' : wsConnected ? 'Relay' : 'Off'}
                </span>
                <span className="metric-key">AI Mode</span>
              </div>
            </div>

            {/* History dots */}
            <div className="section-label" style={{ marginTop: 8 }}>History</div>
            <div className="emotion-history">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className={`hist-dot ${i < emotionHistory.length ? 'active' : ''}`}>
                  {i < emotionHistory.length ? (EMOTION_EMOJI[emotionHistory[i]] ?? '') : ''}
                </div>
              ))}
            </div>
          </div>

          {/* Story map */}
          <div className="scene-list-section">
            <div className="section-label">Story Map</div>
            <StoryMap
              scenesPlayed={scenesPlayed}
              currentEmotion={emotion?.primary_emotion ?? null}
            />
          </div>
        </aside>
      </main>

      {/* ── INFO BAR ── */}
      <div className="info-bar">
        <div className="narration">
          {assets?.narration_text ?? 'Press Start to begin your film.'}
        </div>
        <div className="scene-meta">
          <span className="chapter-name">{assets?.chapter ?? '—'}</span>
          <span className="scene-counter">Scene {scenesPlayed.length}</span>
        </div>
      </div>

      {/* ── CONTROLS ── */}
      <div className="controls">
        <div className="controls-left">
          <select
            className="genre-select"
            value={selectedGenre}
            onChange={e => setSelectedGenre(e.target.value)}
            disabled={appState !== 'idle'}
          >
            {GENRES.map(g => (
              <option key={g} value={g}>{g.charAt(0).toUpperCase() + g.slice(1)}</option>
            ))}
          </select>
          <button
            className="btn primary"
            onClick={handleStart}
            disabled={appState !== 'idle'}
          >
            ▶ Start
          </button>
          <button
            className="btn"
            onClick={handleReset}
            disabled={appState === 'idle' || appState === 'calibrating'}
          >
            ↺ Reset
          </button>
        </div>
        <div className={`status-text ${appState === 'playing' ? 'active' : ''}`}>
          <span className={`ws-dot ${wsConnected ? 'connected' : 'error'}`} />
          {appState === 'idle' && 'Idle — press Start'}
          {appState === 'calibrating' && 'Calibrating…'}
          {(appState === 'playing' || appState === 'deciding') && 'Playing…'}
          {appState === 'ended' && 'Film complete'}
        </div>
      </div>

      {/* ── END SCREEN ── */}
      {appState === 'ended' && (
        <div className="end-screen">
          <div className="end-inner">
            <div className="end-eyebrow">Your Film Has Concluded</div>
            <h2 className="end-title">Your Film DNA</h2>
            <div className="end-rule" />
            <div className="end-ending-name">{ending ? (ENDINGS[ending] ?? ending) : '—'}</div>
            <div className="end-emotion-summary">
              Dominant emotion: {emotionHistory.length > 0
                ? (() => {
                    const freq: Record<string, number> = {}
                    emotionHistory.forEach((e) => { freq[e] = (freq[e] ?? 0) + 1 })
                    const dom = Object.keys(freq).sort((a, b) => freq[b] - freq[a])[0]
                    return `${EMOTION_EMOJI[dom] ?? ''} ${dom}`
                  })()
                : '—'}
            </div>
            <div className="end-scenes">
              <div className="end-scenes-label">Scenes Witnessed</div>
              {scenesPlayed.map((s, i) => (
                <div key={i} className="end-scene-item">
                  <span className="idx">{String(i + 1).padStart(2, '0')}</span>
                  <span>{s.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
            <div className="end-rule" />
            <div className="end-cta">
              <button className="btn primary" onClick={handleReset}>↺ Watch Again</button>
            </div>
          </div>
        </div>
      )}

      {/* Hidden canvas for frame capture */}
      <canvas ref={canvasRef} style={{ display: 'none' }} width={320} height={240} />
      {/* Audio player — autoPlay blocked in some browsers; fall back to a tap-to-play button */}
      {assets?.audio_base64 && (
        <audio
          key={assets.scene_id}
          ref={(el) => {
            audioRef.current = el
            if (el) el.play().catch(() => setAudioBlocked(true))
          }}
          src={`data:audio/wav;base64,${assets.audio_base64}`}
          onEnded={triggerEnded}
          style={{ display: 'none' }}
        />
      )}
      {audioBlocked && (
        <button
          className="btn audio-unblock"
          onClick={() => { audioRef.current?.play(); setAudioBlocked(false) }}
        >
          ▶ Tap to enable audio
        </button>
      )}
    </div>
  )
}
