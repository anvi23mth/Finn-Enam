import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// /research/* is the FINN backend (uvicorn on :8000); proxied in dev so the app can POST /research/{ticker}.
export default defineConfig({ plugins: [react()], server: { proxy: { '/research': 'http://localhost:8000' } } })
