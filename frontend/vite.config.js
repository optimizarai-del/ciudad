import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    // Divide el bundle en chunks para que el navegador descargue en paralelo
    // y pueda cachear vendor libs independientemente del código de la app.
    rollupOptions: {
      output: {
        manualChunks: {
          // React core — cambia muy poco, se cachea por mucho tiempo
          vendor: ['react', 'react-dom', 'react-router-dom'],
          // Íconos — biblioteca grande, se cachea sola
          icons: ['lucide-react'],
        },
      },
    },
    // Umbral de advertencia de chunk: 600 KB (default 500)
    chunkSizeWarningLimit: 600,
  },
})
