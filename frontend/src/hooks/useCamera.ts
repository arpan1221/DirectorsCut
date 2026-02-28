import { useCallback, useRef } from 'react'

export function useCamera() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const startCamera = useCallback(async (): Promise<boolean> => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      return true
    } catch {
      return false
    }
  }, [])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  /** Returns base64 JPEG (no data: prefix) or null if camera not ready */
  const captureFrame = useCallback((): string | null => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || !streamRef.current) return null

    const ctx = canvas.getContext('2d')
    if (!ctx) return null

    canvas.width = 320
    canvas.height = 240
    ctx.drawImage(video, 0, 0, 320, 240)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.7)
    return dataUrl.split(',')[1] ?? null
  }, [])

  return { videoRef, canvasRef, startCamera, stopCamera, captureFrame }
}
