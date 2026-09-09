<script setup>
// 单条消息：user 右对齐气泡；assistant 全宽正文（无容器边框/背景，Claude Code 风格）。
// assistant 内部是一个时间线（timeline）：思考/工具调用/工具结果按发生顺序交错，
// 不同时刻的思考是独立条目，不堆在顶部（④）。
// 工具结果默认折叠（②）：超过 SHORT_LEN 只展示开头，可展开/收起。
// 结构参考 Claude Code：推理是暗色可折叠小块，工具调用是紧凑日志行，答复是正文。
// ③ 输出块图标：思考=CPU(模型推理) / 工具=Tools / 结果=Document，统一走 EP 官方图标库
import { ref, computed, watch, onUnmounted } from 'vue'
import { CaretRight, CaretBottom, Cpu, Tools, Document } from '@element-plus/icons-vue'

const props = defineProps({
  message: { type: Object, required: true },
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
</style>
