// Feature: All features
// Layer:   Config
// Purpose: Vite bundler configuration. Dev server proxies /api to backend.
// API:     None

import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    host: true,
    // Windows Docker bind-mounts don't forward inotify events to the Linux
    // container, so native file-watching misses edits and HMR never fires
    // (the UI looks "stuck" on old code). Polling makes the watcher reliable.
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
