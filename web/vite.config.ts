/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Local development: the FastAPI server (uvicorn fip.api:app --port 8531) answers /api/*.
// On Vercel, /api/* is rewritten to the Python function in api/index.py (see ../vercel.json).
export default defineConfig({
  plugins: [react()],
  server: { port: 5190, proxy: { '/api': 'http://127.0.0.1:8531' } },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: false },
})
