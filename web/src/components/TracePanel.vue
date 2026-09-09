<script setup>
// ④ 会话轨迹展示面板：点头部「轨迹」打开，读当前会话 Agent 实例的内存轨迹（第7课 format_trace 的数据源）。
//
// 和聊天时间线的区别：这里展示的是"幕后完整记录"——每一步的 step 号、耗时、参数、结果
//（含 assistant 最终答复、final_answer 结构化输出、timeout），是审计/复盘的可见入口。
// trace 是 Agent 实例上累积的（跨多次 run 追加），所以同一会话里会越积越长。
import { ref, watch } from 'vue'
import { Cpu, Tools, Document, CircleCheck, Warning, Files, ChatDotRound, CaretRight, CaretBottom } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  sid: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const trace = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  if (!props.sid) { trace.value = []; return }
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch(`/api/sessions/${props.sid}/trace`)
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    const data = await resp.json()
    // 每条加上 open:false —— 轨迹默认折叠（②），点了才展开，扫起来更省力
    trace.value = (data.trace || []).map((ev) => ({ ...ev, open: false }))
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 打开时拉一次；每次打开都重新拉（轨迹随对话增长）
watch(() => props.modelValue, (open) => { if (open) load() })
// ⑤ 会话切换：抽屉开着时换了 sid，也要重新拉（否则显示的是上一个会话的轨迹）
watch(() => props.sid, () => { if (props.modelValue) load() })

// —— 图标 / 标签：与聊天时间线同一套 EP 图标语言（③）。
// 新增两类（② 轨迹补全）：thinking=模型思考（Cpu，模型推理）/ prompt=
// 提示词·上下文（Files，发给模型的消息快照）。assistant 从 Cpu 让给 thinking。
function icon(role) {
  return { tool: Tools, final_answer: CircleCheck, assistant: ChatDotRound,
           thinking: Cpu, prompt: Files, timeout: Warning }[role] || Cpu
}
function label(ev) {
  switch (ev.role) {
    case 'tool': return `调用工具：${ev.name}`
    case 'final_answer': return '最终答复'
    case 'assistant': return '答复'
    case 'thinking': return '模型思考'
    case 'prompt': return `提示词 · 上下文（${ev.args?.n_messages ?? 0} 条消息）`
    case 'timeout': return '达到最大步数，任务未完成'
    default: return ev.role || '事件'
  }
}
function meta(ev) {
  const parts = []
  if (ev.step) parts.push(`step ${ev.step}`)
  if (ev.elapsed != null) parts.push(`${Number(ev.elapsed).toFixed(2)}s`)
  if (ev.ts) parts.push(ev.ts.slice(11))   // 时间戳只取时分秒
  return parts.join(' · ')
}
function body(ev) {
  if (ev.role === 'tool') return `${ev.args} → ${ev.result}`
  if (ev.role === 'final_answer') {
    if (ev.args && typeof ev.args === 'object' && ev.args.summary) return `summary: ${ev.args.summary}`
    return JSON.stringify(ev.args)
  }
  return ev.result || ev.args || ''
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    title="轨迹"
    size="48%"
    class="trace-drawer"
  >
    <div class="tp">
      <div v-if="trace.length" class="tp-summary mono">
        本会话 {{ trace.length }} 个步骤 · 打开时实时拉取
      </div>
      <div v-if="loading" class="tp-state">加载中…</div>
      <div v-else-if="error" class="tp-state tp-error">加载失败：{{ error }}</div>
      <div v-else-if="trace.length === 0" class="tp-state">本会话还没有轨迹。</div>
      <div v-else class="tp-list">
        <div v-for="(ev, i) in trace" :key="i" class="tp-item" :class="ev.role">
          <!-- ① 整条头部可点：展开/收起（默认收起），caret 指示状态（②） -->
          <button class="tp-head" @click="ev.open = !ev.open">
            <el-icon class="caret"><CaretRight v-if="!ev.open" /><CaretBottom v-else /></el-icon>
            <el-icon class="tp-ic" :class="'ic-' + ev.role">
              <component :is="icon(ev.role)" />
            </el-icon>
            <span class="tp-label">{{ label(ev) }}</span>
            <span v-if="meta(ev)" class="tp-meta mono">{{ meta(ev) }}</span>
          </button>
          <div v-if="ev.open" class="tp-body mono">{{ body(ev) }}</div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.tp { display: flex; flex-direction: column; gap: .6rem; }
.tp-summary { font-size: .72rem; color: var(--text-dim); }
.tp-state { color: var(--text-dim); padding: 1rem 0; }
.tp-error { color: var(--error); }
.tp-list { display: flex; flex-direction: column; gap: .5rem; }
/* ③ 每步一张浅色卡片：左边条=事件类型色；卡片内 head 是【图标 · 标签 · 元信息】一行，
   元信息靠右且不换行；body 用细分割线隔开，扫描更省力 */
.tp-item {
  padding: .55rem .7rem;
  border-left: 3px solid;
  border-radius: 0 4px 4px 0;
  background: rgba(15, 23, 32, .35);
  font-size: .8rem;
}
.tp-item.tool { border-left-color: var(--tool); }
.tp-item.assistant { border-left-color: var(--user); }
.tp-item.final_answer { border-left-color: var(--result); }
.tp-item.thinking { border-left-color: var(--think); }
.tp-item.prompt { border-left-color: var(--text-dim); }
.tp-item.timeout { border-left-color: var(--error); }
/* 头部做成整条可点的按钮：caret 指示折叠状态，其余排版不变 */
.tp-head {
  display: flex;
  align-items: center;
  gap: .35rem;
  width: 100%;
  padding: 0;
  margin: 0;
  background: none;
  border: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.tp-head:hover .tp-label { color: var(--text); }
.caret { color: var(--text-dim); font-size: .8rem; flex: none; }
.tp-ic { font-size: .95rem; flex: none; }
.ic-tool { color: var(--tool); }
.ic-assistant { color: var(--user); }
.ic-final_answer { color: var(--result); }
.ic-thinking { color: var(--think); }
.ic-prompt { color: var(--text-dim); }
.ic-timeout { color: var(--error); }
/* 名称（标签）随图标一起着色；只有它带颜色，正文统一灰——突出最终答复（用户要求） */
.tp-label { font-weight: 600; }
.tp-item.tool .tp-label { color: var(--tool); }
.tp-item.assistant .tp-label { color: var(--user); }
.tp-item.final_answer .tp-label { color: var(--result); }
.tp-item.thinking .tp-label { color: var(--think); }
.tp-item.prompt .tp-label { color: var(--text-dim); }
.tp-item.timeout .tp-label { color: var(--error); }
.tp-meta {
  margin-left: auto;
  color: var(--text-dim);
  font-size: .72rem;
  white-space: nowrap;
}
.tp-body {
  margin-top: .3rem;
  padding-top: .35rem;
  border-top: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
  color: var(--text-dim);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  font-size: .8rem;
}
</style>

<!-- 不 scope：el-drawer 会 teleport 到 body，scoped 选择器够不着它；这里统一给抽屉上磨砂玻璃。 -->
<style>
.trace-drawer {
  background: rgba(22, 32, 43, .9) !important;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.trace-drawer .el-drawer__header {
  color: var(--text);
  margin-bottom: 0;
  padding: 1rem 1.2rem .7rem;   /* 上下左右留白：标题和关闭按钮别贴边 */
}
.trace-drawer .el-drawer__body {
  padding: 0 1.2rem 1.4rem;     /* 顶部交给 header 的底部留白，内容只在左右留白 */
}
</style>
