import { useCallback, useRef, useState } from 'react'
import type { BackendMessage, EmotionReading } from '../types'

const WS_PATH = '/ws/session'
const RECONNECT_DELAY_MS = 2500

function buildWsUrl(): string {
  const backendUrl = import.meta.env.VITE_BACKEND_URL as string | undefined
  if (backendUrl) {
    const parsed = new URL(backendUrl)
    const wsProto = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${wsProto}//${parsed.host}${WS_PATH}`
  }
  // Same-origin fallback for local Docker / Vite dev
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}${WS_PATH}`
}

export function useBackendWS(onMessage: (msg: BackendMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return

    const ws = new WebSocket(buildWsUrl())

    ws.onopen = () => setConnected(true)
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data) as BackendMessage
        onMessage(msg)
      } catch {
        console.warn('Unparseable WS message')
      }
    }
    ws.onerror = () => console.error('Backend WS error')
    ws.onclose = () => {
      setConnected(false)
      reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS)
    }

    wsRef.current = ws
  }, [onMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const send = useCallback((payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
    }
  }, [])

  /** Send a pre-computed emotion reading (Gemini Live API path) */
  const sendEmotion = useCallback(
    (reading: EmotionReading) => send({ type: 'emotion', data: reading }),
    [send],
  )

  /** Send a raw webcam frame (backend-side emotion detection path) */
  const sendFrame = useCallback(
    (base64: string) => send({ type: 'frame', data: base64 }),
    [send],
  )

  return { connect, disconnect, send, sendEmotion, sendFrame, connected }
}
