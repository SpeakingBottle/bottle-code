<script setup>
// 聊天页骨架：消息列表 + 输入框 + SSE 消费逻辑
import { ref, reactive, watch, nextTick } from 'vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'

// ---- 会话记忆（10B）：session_id 存 localStorage，刷新后同一会话续上 ----
const sessionId = ref(localStorage.getItem('codeops_session_id') || '')
// 首次加载就生成 session_id：否则发 session_id: null，后端不存会话，记忆不生效
if (!sessionId.value) {
  sessionId.value = crypto.randomUUID()
  localStorage.setItem('codeops_session_id', sessionId.value)
}
const messages = ref([])
const sending = ref(false)

function newSession() {
  sessionId.value = crypto.randomUUID()
  localStorage.setItem('codeops_session_id', sessionId.value)
  messages.value = []
}

// ---- 刷新后恢复聊天记录（10C）：向后端要这个会话的文本历史 ----
// 后端是唯一事实源（Agent.history），前端不自己存消息；
// 工具事件不恢复——它们是单次运行的内部过程，重新对话时会重新产生。
async function restoreHistory() {
  try {
    const resp = await fetch(`/api/sessions/${sessionId.value}/history`)
    if (!resp.ok) return
    const data = await resp.json()
    // 历史里的 assistant 消息是最终答复（可能带 final_answer 的结构化 JSON），
    // 直接按文本消息渲染；streaming=false 表示它已结束。
    messages.value = data.messages.map((m) => ({
      role: m.role, content: m.content, events: [], streaming: false,
    }))
  } catch (e) {
    // 后端没起 / 网络差：静默失败，页面保持空对话，不影响继续使用
  }
}
restoreHistory()

// ---- 消费 SSE 流：和 test.html 同款，但事件写进 Vue 响应式状态 ----
async function send(prompt) {
  if (sending.value) return
  sending.value = true
  messages.value.push({ role: 'user', content: prompt })
  // 必须用 reactive()：push 进数组后，局部变量要持有"响应式代理"本身，
  // 后续 assistant.content += 才会触发重渲染。用普通对象的话，改的是原始对象，
  // 代理的 SET 陷阱不触发，流式文本会"静默丢失"（Vue 3 经典坑）。
  const assistant = reactive({ role: 'assistant', content: '', events: [], streaming: true })
  messages.value.push(assistant)

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, session_id: sessionId.value || null }),
    })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const blocks = buf.split('\n\n')
      buf = blocks.pop()   // 最后一块可能不完整，留到下次
      for (const block of blocks) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        const ev = JSON.parse(line.slice(5).trim())
        handleEvent(ev, assistant)
      }
    }
  } catch (e) {
    assistant.content += '\n[错误] ' + e.message
  } finally {
    assistant.streaming = false
    sending.value = false
  }
}

// 事件协议（与后端一致）：delta 追加文本 / tool+result 进 events / done 用最终答复覆盖
function handleEvent(ev, assistant) {
  if (ev.type === 'delta') assistant.content += ev.text
  else if (ev.type === 'tool') assistant.events.push({ kind: 'tool', name: ev.name, args: ev.args })
  else if (ev.type === 'result') assistant.events.push({ kind: 'result', name: ev.name, text: ev.text })
  else if (ev.type === 'done') assistant.content = ev.text
  else if (ev.type === 'error') assistant.content += '\n[错误] ' + ev.text
}

// 新内容到达时自动滚到底部（deep watch：流式追加也会触发）
const listEl = ref(null)
watch(messages, async () => {
  await nextTick()
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}, { deep: true })
</script>

<template>
  <div class="chat">
    <header class="chat-header">
      <div class="title">
        <!-- 终端提示符样式的标题：`❯` 呼应命令行，而不是一个普通 h1 -->
        <span class="prompt">❯</span>
        <h1>CodeOps Agent</h1>
      </div>
      <div class="header-right">
        <span class="status" title="当前会话标识">#{{ sessionId.slice(0, 8) }}</span>
        <button class="new-session" @click="newSession">新建会话</button>
      </div>
    </header>

    <main class="chat-messages" ref="listEl">
      <ChatMessage v-for="(m, i) in messages" :key="i" :message="m" />
      <!-- 空状态：引导输入，而不是空白一片 -->
      <div v-if="messages.length === 0" class="empty-hint">
        <p class="empty-line mono">$ 输入任务开始对话</p>
        <p class="empty-sub">例如：帮我计算 2+3 的结果</p>
      </div>
    </main>

    <ChatInput :disabled="sending" @send="send" />
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 820px;
  margin: 0 auto;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .7rem 1.1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.title { display: flex; align-items: baseline; gap: .5rem; }
.prompt { color: var(--user); font-family: ui-monospace, Consolas, monospace; font-weight: 700; }
.chat-header h1 { font-size: 1.05rem; margin: 0; font-weight: 600; letter-spacing: .02em; }
.header-right { display: flex; align-items: center; gap: .8rem; }
.status { font-family: ui-monospace, Consolas, monospace; font-size: .75rem; color: var(--text-dim); }
.new-session {
  padding: .35rem .8rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-size: .85rem;
}
.new-session:hover { background: var(--surface-2); border-color: var(--user); }
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.2rem 1.1rem;
  display: flex;
  flex-direction: column;
  gap: .9rem;
}
.empty-hint { text-align: center; margin-top: 4rem; color: var(--text-dim); }
.empty-line { font-size: .95rem; color: var(--user); margin: 0; }
.empty-sub { font-size: .85rem; margin: .4rem 0 0; }
</style>
