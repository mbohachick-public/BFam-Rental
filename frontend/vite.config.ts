import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // So links using http://127.0.0.1:5173 (e.g. FRONTEND_PUBLIC_URL) work alongside http://localhost:5173
    host: true,
    proxy: {
      // Browser calls same-origin /api/*; Vite forwards to FastAPI (avoids CORS during local dev).
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '') || '/',
      },
    },
  },
})
