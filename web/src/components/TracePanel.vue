<script setup>
// ④ 会话轨迹展示面板：点头部「轨迹」打开，读当前会话 Agent 实例的内存轨迹（第7课 format_trace 的数据源）。
//
// 和聊天时间线的区别：这里展示的是"幕后完整记录"——每一步的 step 号、耗时、参数、结果
//（含 assistant 最终答复、final_answer 结构化输出、timeout），是审计/复盘的可见入口。
// trace 是 Agent 实例上累积的（跨多次 run 追加），所以同一会话里会越积越长。
import { ref, watch } from 'vue'
import { Cpu, Tools, Document, CircleCheck, Warning } from '@element-plus/icons-vue'

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
    trace.value = data.trace || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// 打开时拉一次；每次打开都重新拉（轨迹随对话增长）
watch(() => props.modelValue, (open) => { if (open) load() })

// —— 图标 / 标签：与聊天时间线同一套 EP 图标语言（③）——
function icon(role) {
  return { tool: Tools, final_answer: CircleCheck, assistant: Cpu, timeout: Warning }[role] || Cpu
}
function label(ev) {
  switch (ev.role) {
    case 'tool': return `调用工具：${ev.name}`
    case 'final_answer': return '最终答复'
    case 'assistant': return '答复'
    case 'timeout': return '达到最大步数，任务未完成'
    default: return ev.role || '事件'
  }
}
function meta(ev) {
  const parts = []
  if (ev.step) parts.push(`step ${ev.step}`)
  if (ev.elapsed != null) parts.push(`${ev.elapsed}s`)
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
      <div v-if="loading" class="tp-state">加载中…</div>
      <div v-else-if="error" class="tp-state tp-error">加载失败：{{ error }}</div>
      <div v-else-if="trace.length === 0" class="tp-state">本会话还没有轨迹。</div>
      <div v-else class="tp-list">
        <div v-for="(ev, i) in trace" :key="i" class="tp-item" :class="ev.role">
          <div class="tp-head">
            <el-icon class="tp-ic" :class="'ic-' + ev.role">
              <component :is="icon(ev.role)" />
            </el-icon>
            <span class="tp-label">{{ label(ev) }}</span>
            <span v-if="meta(ev)" class="tp-meta mono">{{ meta(ev) }}</span>
          </div>
          <div class="tp-body mono">{{ body(ev) }}</div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.tp { display: flex; flex-direction: column; gap: .5rem; }
.tp-state { color: var(--text-dim); padding: 1rem 0; }
.tp-error { color: var(--error); }
.tp-list { display: flex; flex-direction: column; gap: .4rem; }
.tp-item {
  padding: .45rem .6rem;
  border-left: 3px solid var(--border);
  border-radius: 0 3px 3px 0;
  font-size: .8rem;
}
/* 按事件类型给左边条上语义色，和聊天时间线一致 */
.tp-item.tool { border-left-color: var(--tool); }
.tp-item.assistant { border-left-color: var(--user); }
.tp-item.final_answer { border-left-color: var(--result); }
.tp-item.timeout { border-left-color: var(--error); }
.tp-head { display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
.tp-ic { font-size: .9rem; flex: none; }
.ic-tool { color: var(--tool); }
.ic-assistant { color: var(--user); }
.ic-final_answer { color: var(--result); }
.ic-timeout { color: var(--error); }
.tp-label { font-weight: 600; }
.tp-meta { color: var(--text-dim); font-size: .72rem; margin-left: auto; }
.tp-body {
  margin-top: .2rem;
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  font-size: .78rem;
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
  padding: 0 0 .8rem;
}
.trace-drawer .el-drawer__body {
  padding: 1rem 1.2rem 1.4rem;
}
</style>
