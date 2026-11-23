import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  // 生产包压缩时去掉调试日志（保留 console.warn / console.error 便于排障）
  esbuild: { pure: ['console.log', 'console.debug'] },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-icons': ['@ant-design/icons'],
          'vendor-utils': ['axios', 'dayjs', 'zustand'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
})

