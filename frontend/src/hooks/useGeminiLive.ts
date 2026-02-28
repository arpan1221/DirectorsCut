import { useCallback, useRef, useState } from 'react'
import { GoogleGenAI, Modality } from '@google/genai'
import type { EmotionReading } from '../types'

const SYSTEM_PROMPT = `You are analyzing a viewer's facial expression while they watch a film.
After each image, return ONLY a JSON object — no markdown, no explanation:
{
  "primary_emotion": one of "engaged","bored","confused","amused","tense","surprised","neutral",
  "intensity": integer 1-10,
  "attention": one of "screen","away","uncertain",
  "confidence": float 0.0-1.0
}`

const FALLBACK: EmotionReading = {
  primary_emotion: 'neutral',
  intensity: 5,
  attention: 'uncertain',
  confidence: 0,
}

export function useGeminiLive(onEmotion: (e: EmotionReading) => void) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sessionRef = useRef<any>(null)
  const [connected, setConnected] = useState(false)

  const connect = useCallback(
    async (apiKey: string) => {
      if (!apiKey) {
        console.warn('useGeminiLive: no API key — emotion detection disabled')
        return
      }
      try {
        const ai = new GoogleGenAI({ apiKey })
        const session = await ai.live.connect({
          model: 'models/gemini-2.0-flash-exp',
          config: {
            responseModalities: [Modality.TEXT],
            systemInstruction: {
              parts: [{ text: SYSTEM_PROMPT }],
            },
          },
          callbacks: {
            onopen: () => setConnected(true),
            onmessage: (msg: unknown) => {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const text = (msg as any)?.serverContent?.modelTurn?.parts?.[0]?.text as
                | string
                | undefined
              if (!text) return
              try {
                const parsed = JSON.parse(text.trim()) as EmotionReading
                onEmotion(parsed)
              } catch {
                onEmotion(FALLBACK)
              }
            },
            onerror: (e: unknown) => console.error('Gemini Live error:', e),
            onclose: () => setConnected(false),
          },
        })
        sessionRef.current = session
      } catch (e) {
        console.error('Failed to connect to Gemini Live API:', e)
      }
    },
    [onEmotion],
  )

  /**
   * Send a webcam frame to Gemini Live API.
   * sendRealtimeInput streams the frame; sendClientContent triggers analysis.
   */
  const sendFrame = useCallback((base64: string) => {
    const session = sessionRef.current
    if (!session) return
    try {
      session.sendRealtimeInput({ video: { data: base64, mimeType: 'image/jpeg' } })
      // Explicit text turn to guarantee a JSON response for each frame
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(session as any).sendClientContent?.({
        turns: [{ role: 'user', parts: [{ text: 'Analyze the emotion in this frame.' }] }],
        turnComplete: true,
      })
    } catch (e) {
      console.warn('sendFrame error:', e)
    }
  }, [])

  const disconnect = useCallback(() => {
    try {
      sessionRef.current?.close()
    } catch {}
    sessionRef.current = null
    setConnected(false)
  }, [])

  return { connect, disconnect, sendFrame, connected }
}
