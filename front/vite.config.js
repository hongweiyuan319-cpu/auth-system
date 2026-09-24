import { defineConfig } from 'vite'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] })
  ],
  server: {
    // 开发时把 /api 开头的请求转发给本地 Flask。
    // 为什么需要它：request.js 里的 baseURL 是空的（相对路径），
    // 前端发出去的请求是 /api/login。如果不转发，浏览器会认为
    // 「/api/login 是 vite 自己 5173 端口上的路径」→ 404 Not Found。
    // 配上之后：本地开发走 vite 代理，Docker 里走 nginx 代理，
    // 前端代码两边一致，不需要为环境改代码。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
})
