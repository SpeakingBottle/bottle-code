// Vue 入口：挂载 App 到 #app
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// EP 深色模式：html.dark 时启用（index.html 已加 class="dark"），
// 具体颜色在 style.css 里用 CSS 变量覆盖成终端风
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import './style.css'

createApp(App).use(ElementPlus).mount('#app')
