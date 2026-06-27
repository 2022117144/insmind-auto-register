import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from "url"

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5175,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/thumbnails': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/screenshots': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/outputs': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://127.0.0.1:8005',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
