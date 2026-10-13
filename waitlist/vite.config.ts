import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The page talks only to the GTMX API under /api: same origin in production
// (nginx proxies gtmx.co/api), proxied to the local backend in development.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
