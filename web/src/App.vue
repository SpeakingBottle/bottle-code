<script setup>
// 聊天页骨架：消息列表 + 输入框 + SSE 消费逻辑
import { ref, reactive, nextTick } from 'vue'
import { Plus, Memo, ChatDotRound } from '@element-plus/icons-vue'
import ChatMessage from './components/ChatMessage.vue'
import ChatInput from './components/ChatInput.vue'
import TracePanel from './components/TracePanel.vue'
import SessionPanel from './components/SessionPanel.vue'

// ---- 会话记忆（10B）：session_id 存 localStorage，刷新后同一会话续上 ----
const sessionId = ref(localStorage.getItem('codeops_session_id') || '')
// 首次加载就生成 session_id：否则发 session_id: null，后端不存会话，记忆不生效
if (!sessionId.value) {
  sessionId.value = crypto.randomUUID()
  localStorage.setItem('codeops_session_id', sessionId.value)
}
const messages = ref([])
const sending = ref(false)
const traceOpen = ref(false)   // ④ 会话轨迹展示抽屉的开关
const sessionOpen = ref(false) // ⑤ 会话列表抽屉的开关
const sessionPanel = ref(null) // ⑤ 引用子组件：对话结束后刷新列表

function newSession() {
  sessionId.value = crypto.randomUUID()
  localStorage.setItem('codeops_session_id', sessionId.value)
  messages.value = []
}

// ---- ⑤ 会话切换：换 session_id → 清空消息 → 拉新会话的历史 ----
function switchSession(sid) {
  if (sid === sessionId.value) return
  sessionId.value = sid
  localStorage.setItem('codeops_session_id', sid)
  messages.value = []
  restoreHistory()
}
// 当前会话被删了 → 落到一个全新会话（否则页面还指着已删除的 sid）
function onSessionDeleted(sid) {
  if (sid === sessionId.value) newSession()
}

// ---- 刷新后恢复聊天记录（10C）：向后端要这个会话的文本历史 ----
// 后端是唯一事实源（Agent.history），前端不自己存消息；
// 工具事件/推理不恢复——它们是单次运行的内部过程，重新对话时会重新产生。
async function restoreHistory() {
  try {
    const resp = await fetch(`/api/sessions/${sessionId.value}/history`)
    if (!resp.ok) return
    const data = await resp.json()
    messages.value = data.messages.map((m) => ({
      role: m.role, content: m.content, pending: '', timeline: [], streaming: false,
    }))
    scrollToBottom()   // 刚加载完，强制滚到底部
  } catch (e) {
    // 后端没起 / 网络差：静默失败，页面保持空对话，不影响继续使用
  }
}
restoreHistory()

// ---- 消费 SSE 流：和 test.html 同款，但事件写进 Vue 响应式状态 ----
async function send(prompt) {
  if (sending.value) return
  sending.value = true
  // 必须用 reactive()：push 进数组后，局部变量要持有"响应式代理"本身，
  // 后续 assistant.content += 才会触发重渲染。用普通对象的话，改的是原始对象，
  // 代理的 SET 陷阱不触发，流式文本会"静默丢失"（Vue 3 经典坑）。
  messages.value.push({ role: 'user', content: prompt })
  const assistant = reactive({
    role: 'assistant', content: '', pending: '', timeline: [], streaming: true,
  })
  messages.value.push(assistant)
  scrollToBottom()

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, session_id: sessionId.value || null }),
    })
    if (!resp.ok) {
      // 502 = Vite 代理转发失败：后端没在 :8000 跑。给可行动提示，而不是裸报 502。
      const hint = resp.status === 502
        ? '后端未启动（Vite 连不上 :8000）。请运行 start.bat，或单独启动 web/server.py。'
        : 'HTTP ' + resp.status
      throw new Error(hint)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const blocks = buf.split('\n\n')
      buf = blocks.pop()   // 最后一块可能不完整，留到下次
      if (!blocks.length) continue
      // 先记住"进入这块数据前是不是在底部"，内容追加后再决定要不要跟滚：
      // 在底部=跟滚；用户往上翻历史=不打扰。折叠/展开思考不经过这里=不会跳底（⑤）。
      const wasNearBottom = isNearBottom()
      for (const block of blocks) {
        const line = block.trim()
        if (!line.startsWith('data:')) continue
        handleEvent(JSON.parse(line.slice(5).trim()), assistant)
      }
      if (wasNearBottom) scrollToBottom()
    }
  } catch (e) {
    // 网络层失败（Failed to fetch）= 后端没起；同样是给可行动的提示
    const msg = /fetch/i.test(e.message) ? '无法连接后端 :8000，请先运行 start.bat 启动后端。' : e.message
    assistant.content += '\n[错误] ' + msg
    scrollToBottom()
  } finally {
    assistant.streaming = false
    sending.value = false
    // ⑤ 对话结束：会话列表可能变了（新会话/新消息/自动命名），刷新一下
    if (sessionOpen.value) sessionPanel.value?.load()
  }
}

// ---- 事件处理：delta 先缓冲，看到后续事件才知道它是"推理"还是"答复" ----
// 流式协议里文本只有 delta 一种，但语义有两种：
//   工具调用前的文本 = 推理（ReAct 的"思考"）→ 提交进 timeline 的 reason 条目
//   没有工具调用、直接 done 的文本 = 最终答复 → 成为 content
// 所以 delta 先进 pending 缓冲，等下一个事件来裁决：
//   tool 事件 → pending 是推理，flush 成一条 reason
//   done 事件 → pending 丢弃，答复以 done.text 为准（后端已 clean 成干净文本）
// 这就是"协议不变、展示层自己判断"——后端不用为推理单独加事件类型。
function handleEvent(ev, assistant) {
  if (ev.type === 'delta') {
    assistant.pending += ev.text
  } else if (ev.type === 'tool') {
    flushReason(assistant)
    // final_answer 是收尾工具，它的参数就是那堆结构化 JSON，人不用看，过滤掉
    if (ev.name !== 'final_answer') {
      assistant.timeline.push({ kind: 'tool', name: ev.name, args: ev.args })
    }
  } else if (ev.type === 'result') {
    if (ev.name !== 'final_answer') {
      // open:false = 工具结果默认折叠（②：只展示一部分，超长可展开）
      assistant.timeline.push({ kind: 'result', name: ev.name, text: ev.text, open: false })
    }
  } else if (ev.type === 'done') {
    assistant.pending = ''
    assistant.content = ev.text
  } else if (ev.type === 'error') {
    assistant.content += '\n[错误] ' + ev.text
  }
}

// 每次 tool 事件前 flush 一次 → 不同时刻的思考是独立条目，
// 在 timeline 里和工具调用按发生顺序交错，不堆在顶部（④）。
function flushReason(assistant) {
  if (assistant.pending.trim()) {
    assistant.timeline.push({ kind: 'reason', text: assistant.pending, open: true })
  }
  assistant.pending = ''
}

// ---- 自动滚底（⑤）：只在新数据到达时触发 ----
// 不用 deep watch：watch 监听一切变更，折叠/展开思考也会触发滚动 → 页面跳底。
// 改为显式调用：新消息 / 新数据块到达时才滚，且只在用户本来就在底部时跟滚。
const listEl = ref(null)
function isNearBottom() {
  const el = listEl.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}
async function scrollToBottom() {
  await nextTick()
  const el = listEl.value
  if (el) el.scrollTop = el.scrollHeight
}
</script>

<template>
  <div class="app">
    <!-- 头部全宽：横贯整个浏览器，不随内容列限宽 -->
    <header class="chat-header">
      <div class="title">
        <!-- 终端提示符样式的标题：`❯` 呼应命令行，而不是一个普通 h1 -->
        <span class="prompt">❯</span>
        <h1>CodeOps Agent</h1>
      </div>
      <div class="header-right">
        <el-tooltip :content="sessionId" placement="bottom">
          <span class="status mono">#{{ sessionId.slice(0, 8) }}</span>
        </el-tooltip>
        <!-- ⑤ 会话列表入口：回到之前的对话 / 改名 / 删除 -->
        <el-button size="small" :icon="ChatDotRound" @click="sessionOpen = true">会话</el-button>
        <!-- ④ 会话轨迹入口：打开抽屉看本会话的完整轨迹 -->
        <el-button size="small" :icon="Memo" @click="traceOpen = true">轨迹</el-button>
        <el-button size="small" :icon="Plus" @click="newSession">新建会话</el-button>
      </div>
    </header>

    <!-- 内容列：消息 + 输入框，居中限宽（--content-width） -->
    <div class="chat-body">
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

    <TracePanel v-model="traceOpen" :sid="sessionId" />
    <SessionPanel
      v-model="sessionOpen"
      :current-sid="sessionId"
      @select="switchSession"
      @deleted="onSessionDeleted"
      ref="sessionPanel"
    />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .7rem 1.4rem;
  /* ② 头部改磨砂玻璃：苔藓若隐若现，文字依然清晰 */
  background: rgba(22, 32, 43, .6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid color-mix(in srgb, var(--border) 70%, transparent);
}
.title { display: flex; align-items: baseline; gap: .5rem; }
.prompt { color: var(--user); font-family: ui-monospace, Consolas, monospace; font-weight: 700; }
.chat-header h1 { font-size: 1.05rem; margin: 0; font-weight: 600; letter-spacing: .02em; }
.header-right { display: flex; align-items: center; gap: .8rem; }
.status { font-size: .75rem; color: var(--text-dim); cursor: default; }
.chat-body {
  flex: 1;
  min-height: 0;   /* 让内部滚动生效：flex 子项默认 min-height:auto 会撑破父容器 */
  width: 100%;
  max-width: var(--content-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}
/* ① 消息列表滚动条贴输入框 → 隐藏滚动条（滚动功能保留），并给底部留白，
   最后一条内容不和输入框挨着 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.2rem 1.1rem 2.5rem;
  display: flex;
  flex-direction: column;
  gap: .9rem;
  scrollbar-width: none;                      /* Firefox */
}
.chat-messages::-webkit-scrollbar { display: none; }  /* Chrome/Edge/Safari */
.empty-hint { text-align: center; margin-top: 4rem; color: var(--text-dim); }
.empty-line { font-size: .95rem; color: var(--user); margin: 0; }
.empty-sub { font-size: .85rem; margin: .4rem 0 0; }
</style>
