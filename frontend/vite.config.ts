import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import path from "path"
import tailwindcss from "@tailwindcss/vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
        proxy.on("error", (err) => console.log("proxy error:", err))
        proxy.on("proxyReqWs", (_proxyReq, req) => console.log("upgrade req:", req.url))
        proxy.on("open", () => console.log("proxy ws opened"))
        proxy.on("close", () => console.log("proxy ws closed"))
      },
      },
    },
  },
})
