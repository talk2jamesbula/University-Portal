import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development, API and Django admin requests are proxied to Django so no CORS setup is needed.
// The browser's Host header is passed through unchanged (no changeOrigin): Django's CSRF check
// compares it with the Origin header, and rewriting it breaks admin login and logout.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/api', '/admin', '/static', '/media'].map((path) => [
        path,
        { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000' },
      ]),
    ),
  },
})
