import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 开发期代理到 FastAPI（Spec 00 §5.3 联调约定）
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
