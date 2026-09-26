import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 本地开发时 /api 直连本机 gates 服务; Compose 内由 nginx 反代。
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.GATES_URL || 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
})
