import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The page talks only to the Thalace API under /api: same origin in production
// (nginx proxies thalace.com/api), proxied to the local backend in development.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    // GTMX_API_URL points dev at another backend (e.g. one on a test database).
    proxy: { '/api': process.env.GTMX_API_URL ?? 'http://localhost:8000' },
  },
})
