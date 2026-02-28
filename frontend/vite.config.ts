import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy: forward /api and /ws to backend running on 8000
// In production, nginx handles this proxying.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
