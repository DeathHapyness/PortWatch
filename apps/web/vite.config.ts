import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    proxy: {
      // ws: true so the /api/v1/events WebSocket upgrade proxies too —
      // Vite's proxy does not forward WS upgrades by default, only plain
      // HTTP. Harmless for the rest of /api/*, which is plain HTTP.
      '/api': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
})
