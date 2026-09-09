<script setup>
// 单条消息：user 右对齐青色；assistant 左对齐，含推理块 + 工具事件 + 答复文本。
// 结构参考 Claude Code：推理（思考）是可折叠的暗色块，工具调用是紧凑日志行，
// 最终答复是干净的正文。颜色复用全局 token（style.css 的 :root）。
import { CaretRight, CaretBottom } from '@element-plus/icons-vue'

defineProps({
  message: { type: Object, required: true },
})
</script>

<template>
  <div class="message" :class="message.role">
    <div class="bubble">
      <div class="role">{{ message.role === 'user' ? '你' : 'agent' }}</div>

      <template v-if="message.role === 'assistant'">
        <!-- 推理过程：Claude Code 风格的可折叠"思考"块。
             thinking[] = 已提交的推理段（每个 tool 事件前 flush 一次）；
             pending = 正在流式的文本（还没裁决是推理还是答复）。 -->
        <div v-if="message.thinking.length || message.pending" class="thinking">
          <button class="thinking-toggle" @click="message.showThinking = !message.showThinking">
            <el-icon class="caret">
              <CaretRight v-if="!message.showThinking" />
              <CaretBottom v-else />
            </el-icon>
            <span class="thinking-label">思考</span>
          </button>
          <div v-if="message.showThinking" class="thinking-body">
            <div v-for="(t, i) in message.thinking" :key="i" class="thinking-block">{{ t }}</div>
            <div v-if="message.pending" class="thinking-block pending">
              {{ message.pending }}<span v-if="message.streaming" class="cursor">▍</span>
            </div>
          </div>
        </div>

        <!-- 工具事件：终端日志行。tool 先出现（调用了什么），result 跟在后面 -->
        <div v-for="(ev, i) in message.events" :key="i" class="event" :class="ev.kind">
          <span v-if="ev.kind === 'tool'" class="mono">
            <span class="sig">❯</span> {{ ev.name }}({{ ev.args }})
          </span>
          <span v-else class="mono">
            <span class="sig">→</span> {{ ev.name }}: {{ ev.text }}
          </span>
        </div>

        <!-- 最终答复：done 事件一次性写入（后端已 clean 成干净文本） -->
        <div class="text">{{ message.content }}<span v-if="message.streaming && message.content" class="cursor">▍</span></div>
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

/* 推理块：暗色、可折叠，与工具事件同宽（左边延到气泡边缘） */
.thinking {
  margin: .3rem 0 .3rem -.85rem;
  padding: .25rem .5rem .25rem .7rem;
  border-left: 3px solid var(--text-dim);
  border-radius: 0 3px 3px 0;
  background: var(--surface-2);
  font-size: .78rem;
}
.thinking-toggle {
  display: flex;
  align-items: center;
  gap: .35rem;
  background: none;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  padding: .1rem 0;
  font-size: .78rem;
}
.thinking-toggle:hover { color: var(--text); }
.caret { font-size: .8rem; }
.thinking-label { font-weight: 600; }
.thinking-body {
  margin-top: .3rem;
  display: flex;
  flex-direction: column;
  gap: .3rem;
}
.thinking-block {
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

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
