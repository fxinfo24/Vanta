import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Only React is pinned to a chunk. Naming recharts here looked like
        // splitting, but a named manual chunk is preloaded from index.html for
        // every route, so the charting library (156 kB compressed) downloaded
        // on the sign-in screen too. Leaving it unnamed lets Rollup keep it in
        // the lazy chunk of the two views that actually draw charts.
        manualChunks: {
          vendor: ['react', 'react-dom']
        }
      }
    }
  }
})