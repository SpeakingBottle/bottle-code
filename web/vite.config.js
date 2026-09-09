// Vite 配置：Vue 插件 + 开发期代理
// 代理的作用：浏览器只请求 :5173 的 /api，Vite 转发到 :8000 的 FastAPI。
// 浏览器眼里是同源请求，不触发 CORS（后端 CORS 是给直连 :8000 的 test.html 留的）。
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
