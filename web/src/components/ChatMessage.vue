<script setup>
// 单条消息：user 右对齐气泡；assistant 全宽正文（无容器边框/背景，Claude Code 风格）。
// assistant 内部是一个时间线（timeline）：思考/工具调用/工具结果按发生顺序交错，
// 不同时刻的思考是独立条目，不堆在顶部（④）。
// 工具结果默认折叠（②）：超过 SHORT_LEN 只展示开头，可展开/收起。
// 结构参考 Claude Code：推理是暗色可折叠小块，工具调用是紧凑日志行，答复是正文。
// ③ 输出块图标：思考=CPU(模型推理) / 工具=Tools / 结果=Document，统一走 EP 官方图标库
import { ref, computed, watch, onUnmounted } from 'vue'
import { CaretRight, CaretBottom, Cpu, Tools, Document } from '@element-plus/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  message: { type: Object, required: true },
})

// 最终答复是 markdown（模型自然输出：标题/列表/代码块），用 marked 渲染 + DOMPurify 消毒（防 XSS）。
// 只在 done 事件 content 一次性写入时渲染一次（App.vue 里 content 仅 done 时赋值），
// 流式 pending 保持纯文本，不参与渲染——无逐字渲染的性能问题。
const renderedContent = computed(() => {
  const c = props.message.content
  if (!c) return ''
  return DOMPurify.sanitize(marked.parse(c))
})

// 工具结果超过这个长度就默认截断 + 「展开」
const SHORT_LEN = 100

// —— ③ 模型"正在思考但还没有任何可见输出"时的动画（Claude Code 风格）——
// 什么时候算"在思考"？流式中还没产出：内容/未裁决文本(pending)/工具结果，
// 且 timeline 要么空（开局）、要么上一条刚是 result（上一步工具跑完、模型在琢磨下一步）。
// 这时界面上如实反映"模型在工作"，而不是让用户盯着黑屏等 token。
const THINKING_LABELS = ['思考中', '分析中', '推理中', '计算中', '整理中', '编译中']
const labelIdx = ref(0)
let thinkTimer = null
const showThinking = computed(() => {
  const m = props.message
  if (!m.streaming || m.content || m.pending) return false
  const tl = m.timeline
  if (tl.length === 0) return true
  return tl[tl.length - 1].kind === 'result'
})
// 状态词轮换：只在"显示中"才跑定时器，避免无谓开销
watch(showThinking, (on) => {
  if (on) {
    labelIdx.value = 0
    thinkTimer = setInterval(() => { labelIdx.value = (labelIdx.value + 1) % THINKING_LABELS.length }, 700)
  } else if (thinkTimer) {
    clearInterval(thinkTimer); thinkTimer = null
  }
})
onUnmounted(() => { if (thinkTimer) clearInterval(thinkTimer) })
</script>

<template>
  <div class="message" :class="message.role">
    <div class="bubble">
      <!-- 用户消息标注角色；assistant 全宽正文不标（Claude Code 风格） -->
      <div v-if="message.role === 'user'" class="role">你</div>

      <template v-if="message.role === 'assistant'">
        <!-- 时间线：思考/工具/结果按发生顺序交错 -->
        <template v-for="(ev, i) in message.timeline" :key="i">
          <!-- 推理：每条独立、可折叠（③ 加图标 + 说明文字） -->
          <div v-if="ev.kind === 'reason'" class="think">
            <button class="think-toggle" @click="ev.open = !ev.open">
              <el-icon class="ticon ticon-reason"><Cpu /></el-icon>
              <span class="think-label">思考</span>
              <el-icon class="caret"><CaretRight v-if="!ev.open" /><CaretBottom v-else /></el-icon>
            </button>
            <div v-if="ev.open" class="think-body">{{ ev.text }}</div>
          </div>

          <!-- 工具调用（③） -->
          <div v-else-if="ev.kind === 'tool'" class="event tool">
            <span class="ev-head">
              <el-icon class="ticon ticon-tool"><Tools /></el-icon>
              <span class="ev-tag">调用工具</span>
              <span class="mono ev-call">{{ ev.name }}({{ ev.args }})</span>
            </span>
          </div>

          <!-- 工具结果：短结果直接展示；长结果默认截断 + 「展开/收起」（②） -->
          <div v-else class="event result">
            <span class="ev-head">
              <el-icon class="ticon ticon-result"><Document /></el-icon>
              <span class="ev-tag">工具结果</span>
              <span class="mono ev-call">{{ ev.name }}</span>
            </span>
            <div class="ev-body">
              <span v-if="ev.text.length <= SHORT_LEN" class="mono result-text">{{ ev.text }}</span>
              <template v-else>
                <span class="mono result-text">{{ ev.open ? ev.text : ev.text.slice(0, SHORT_LEN) + '…' }}</span>
                <button class="expand-btn" @click="ev.open = !ev.open">{{ ev.open ? '收起' : '展开' }}</button>
              </template>
            </div>
          </div>
        </template>

        <!-- ③ 模型思考中：还没有任何可见输出 → 转圈 + 轮换状态词（Claude Code 风格），
             不阻塞：首个 delta / tool / done 一到，它就自动让位给真实内容 -->
        <div v-if="showThinking" class="thinking-indicator">
          <span class="spinner"></span>
          <span class="thinking-word">{{ THINKING_LABELS[labelIdx] }}<span class="dots">…</span></span>
        </div>

        <!-- 正在流式的未裁决文本：是推理还是答复还没确定，暗色展示 -->
        <div v-if="message.pending" class="pending mono">
          {{ message.pending }}<span v-if="message.streaming" class="cursor">▍</span>
        </div>

        <!-- 最终答复：done 事件一次性写入（后端已 clean 成干净文本）；markdown 渲染 + 消毒 -->
        <div class="text">
          <div v-if="renderedContent" class="md" v-html="renderedContent"></div>
          <span v-if="message.streaming && message.content" class="cursor">▍</span>
        </div>
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
/* ③ assistant 全宽正文：不显示容器边框和背景，宽度铺满内容列（输入框范围内） */
.message.assistant .bubble {
  max-width: 100%;
  width: 100%;
  padding: .15rem 0;
  background: transparent;
  border: none;
}
/* 用户消息只有右侧圆角变 0，形成"从边沿冒出来"的方向感 */
.message.user .bubble {
  background: color-mix(in srgb, var(--user) 12%, transparent);
  border-color: color-mix(in srgb, var(--user) 35%, transparent);
}
.role { font-size: .7rem; color: var(--user); margin-bottom: .25rem; }

/* ---- 时间线条目：思考 / 工具 / 结果 ---- */
/* ① 去掉输出块背景色：不再有实心底，事件直接落在页面背景上（与②苔藓呼应），
   只留左侧语义色边条 + 图标/标签区分类型。
   思考改为专用蓝 --think（区别于 --user 主题蓝）：推理是过程，用户消息是角色。 */
.think {
  margin: .3rem 0;
  padding: .2rem 0 .3rem .55rem;
  border-left: 3px solid var(--think);
  border-radius: 0 3px 3px 0;
  background: transparent;
  font-size: .78rem;
}
.think-toggle {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  background: none;
  border: none;
  color: var(--think);
  cursor: pointer;
  padding: .1rem 0;
  font-size: .78rem;
  font-family: inherit;
}
.think-toggle:hover { color: var(--text); }
.caret { font-size: .8rem; }
.think-label { font-weight: 600; }
.think-body {
  margin-top: .3rem;
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

/* 工具调用/结果 = 终端日志行：左侧语义色边条 + 图标/标签 + 等宽内容 */
.event {
  margin: .3rem 0;
  padding: .25rem 0 .3rem .55rem;
  border-left: 3px solid;
  border-radius: 0 3px 3px 0;
  background: transparent;
  font-size: .78rem;
  line-height: 1.45;
}
.event.tool { border-left-color: var(--tool); color: var(--tool); }
.event.result { border-left-color: var(--result); color: var(--result); }

/* ③ 图标 + 说明文字：一行【图标 · 标签 · 内容】，图标颜色继承事件语义色 */
.ev-head { display: inline-flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
/* 只有图标 + 语义标签带颜色（继承 .event 的类型色）；正文/参数这些"数据"统一灰，
   让最终答复正文（.text=亮色）成为视觉焦点（用户要求） */
.ev-tag { font-weight: 600; }
.ev-call { color: var(--text-dim); word-break: break-all; }
.ev-body { margin-top: .25rem; }
.ticon { font-size: .85rem; flex: none; }
.ticon-reason { color: var(--think); }
.ticon-tool { color: var(--tool); }
.ticon-result { color: var(--result); }
.result-text { color: var(--text-dim); word-break: break-all; }
.expand-btn {
  margin-left: .5rem;
  padding: 0 .35rem;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: transparent;
  color: var(--text-dim);
  font-size: .7rem;
  cursor: pointer;
  font-family: inherit;
}
.expand-btn:hover { color: var(--text); border-color: var(--user); }

/* 流式中的未裁决文本：暗色，和最终答复区分 */
.pending {
  margin: .3rem 0;
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  font-size: .88rem;
}

/* ③ 模型思考中动画：转圈 + 轮换状态词，蓝色（--think），不占内容位置 */
.thinking-indicator {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  margin: .3rem 0;
  color: var(--think);
  font-size: .82rem;
}
.spinner {
  width: .78rem;
  height: .78rem;
  flex: none;
  border: 2px solid color-mix(in srgb, var(--think) 22%, transparent);
  border-top-color: var(--think);
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
.thinking-word { font-weight: 600; }
.dots { animation: blink 1.2s steps(1) infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.text { white-space: pre-wrap; word-break: break-word; font-size: .95rem; line-height: 1.6; }
.cursor {
  color: var(--user);
  animation: blink 1s steps(1) infinite;
}
@keyframes blink { 50% { opacity: 0; } }

/* ---- markdown 渲染（最终答复）：深色终端风，与全局 token 一致 ---- */
/* .text 的 pre-wrap 会破坏 HTML 布局，md 块内恢复 normal */
.md { white-space: normal; word-break: break-word; line-height: 1.65; }
.md > :first-child { margin-top: 0; }
.md > :last-child { margin-bottom: 0; }
.md h1, .md h2, .md h3, .md h4 {
  margin: 1.1em 0 .5em;
  line-height: 1.3;
  color: var(--text);
}
.md h1 { font-size: 1.25rem; border-bottom: 1px solid var(--border); padding-bottom: .3em; }
.md h2 { font-size: 1.12rem; }
.md h3 { font-size: 1.02rem; }
.md h4 { font-size: .95rem; }
.md p { margin: .5em 0; }
.md ul, .md ol { margin: .5em 0; padding-left: 1.4em; }
.md li { margin: .2em 0; }
.md a { color: var(--user); text-decoration: none; }
.md a:hover { text-decoration: underline; }
.md strong { color: var(--text); }
/* 行内代码：暗底小圆角 */
.md :not(pre) > code {
  background: rgba(15, 23, 32, .55);
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: .08em .35em;
  font-size: .85em;
  font-family: Consolas, 'Courier New', monospace;
}
/* 代码块：暗底 + 边框 + 横向滚动 */
.md pre {
  background: rgba(15, 23, 32, .55);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: .6rem .8rem;
  overflow-x: auto;
  font-size: .8rem;
  line-height: 1.5;
}
.md pre code {
  background: none;
  border: none;
  padding: 0;
  font-size: inherit;
  font-family: Consolas, 'Courier New', monospace;
}
.md blockquote {
  margin: .5em 0;
  padding: .1em .9em;
  border-left: 3px solid var(--border);
  color: var(--text-dim);
}
.md hr { border: none; border-top: 1px solid var(--border); margin: 1em 0; }
.md table { border-collapse: collapse; margin: .6em 0; font-size: .88rem; }
.md th, .md td { border: 1px solid var(--border); padding: .35em .6em; }
.md th { background: rgba(15, 23, 32, .4); }
</style>
