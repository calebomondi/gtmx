import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"
import path from "node:path"

// The preview proxy reaches the dev server through a rotating sandbox host and
// sends the public preview origin, so both have to be allowed in the sandbox.
// Outside the preview flag the allowlist stays at the framework defaults.
const previewMode = process.env.BASE44_PREVIEW_MODE === "1"
const allowedHosts = ["localhost", "127.0.0.1"]
if (previewMode) {
  const publicSuffix = process.env.BASE44_PUBLIC_HOST_SUFFIX
  const sandboxDomain = process.env.BASE44_SANDBOX_HOST_DOMAIN
  if (publicSuffix) allowedHosts.push(`3000-${publicSuffix}`)
  if (sandboxDomain) allowedHosts.push(`.${sandboxDomain}`)
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 3000,
    strictPort: true,
    allowedHosts,
  },
})
