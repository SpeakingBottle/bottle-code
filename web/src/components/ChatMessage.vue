<script setup>
// 单条消息：user 右对齐青色；assistant 左对齐，含工具事件 + 流式文本 + 光标。
// 工具事件用终端日志样式：左边一条语义色边条 + 等宽字体，
// tool=琥珀（❯ 调用了什么）/ result=绿（→ 返回了什么），
// 颜色复用全局 token（style.css 的 :root），scoped 里能读到。
defineProps({
  message: { type: Object, required: true },
})
</script>

<template>
  <div class="message" :class="message.role">
    <div class="bubble">
      <div class="role">{{ message.role === 'user' ? '你' : 'agent' }}</div>

      <template v-if="message.role === 'assistant'">
        <!-- 工具事件：终端日志行。tool 先出现（调用了什么），result 跟在后面 -->
        <div v-for="(ev, i) in message.events" :key="i" class="event" :class="ev.kind">
          <span v-if="ev.kind === 'tool'" class="mono">
            <span class="sig">❯</span> {{ ev.name }}({{ ev.args }})
          </span>
          <span v-else class="mono">
            <span class="sig">→</span> {{ ev.name }}: {{ ev.text }}
          </span>
        </div>
        <!-- 流式文本：delta 追加到这里；生成中显示闪烁光标（终端光标 ▍） -->
        <div class="text">{{ message.content }}<span v-if="message.streaming" class="cursor">▍</span></div>
      </template>

      <div v-else class="text">{{ message.content }}</div>
    </div>
  </div>
</template>

<style scoped>
.message { display: flex; }
.message.user { justify-content: flex-end; }
.bubble {
  max-width: 80%;
  padding: .5rem .85rem;
  border-radius: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
}
/* 用户消息只有右侧圆角变 0，形成"从边沿冒出来"的方向感（终端风，不做大圆角卡片） */
.message.user .bubble {
  background: color-mix(in srgb, var(--user) 12%, transparent);
  border-color: color-mix(in srgb, var(--user) 35%, transparent);
}
.role { font-size: .7rem; color: var(--text-dim); margin-bottom: .25rem; }
.message.user .role { color: var(--user); }

/* 工具事件 = 终端日志行：左侧语义色边条 + 等宽字体 */
.event {
  margin: .3rem 0 .3rem -.85rem;   /* 左边延到气泡边缘，边条顶到气泡左上 */
  padding: .25rem .5rem .25rem .7rem;
  border-left: 3px solid;
  border-radius: 0 3px 3px 0;
  background: var(--surface-2);
  font-size: .78rem;
  word-break: break-all;
  line-height: 1.45;
}
.event.tool { border-left-color: var(--tool); color: var(--tool); }
.event.result { border-left-color: var(--result); color: var(--result); }
.sig { font-weight: 700; }
.text { white-space: pre-wrap; word-break: break-word; font-size: .95rem; line-height: 1.6; }
.cursor {
  color: var(--user);
  animation: blink 1s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }
</style>
