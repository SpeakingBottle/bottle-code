<script setup>
// ⑤ 会话列表面板：点头部「会话」打开。列历史会话，可切换 / 行内改名 / 删除。
// 数据来自 GET /api/sessions（后端从落盘的 session_meta + chat_logs 组装）。
// 与 TracePanel 同款磨砂抽屉；行内改名用 el-input 替换名称，删除用 el-popconfirm 确认。
import { ref, watch } from 'vue'
import { ChatDotRound, Edit, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  currentSid: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'select', 'deleted'])

const sessions = ref([])
const loading = ref(false)
const error = ref('')
const editingSid = ref('')   // 正在行内改名的会话（空 = 没有在改）
const editName = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const resp = await fetch('/api/sessions')
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    const data = await resp.json()
    sessions.value = data.sessions || []
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
// 打开时拉一次；App 在每次对话结束后也会调 load() 刷新（新消息/新会话/自动命名）
watch(() => props.modelValue, (open) => { if (open) load() })
defineExpose({ load })

function pick(s) {
  if (s.sid === props.currentSid) return   // 已经是当前会话，不用切
  emit('select', s.sid)
}

function startRename(s) {
  editingSid.value = s.sid
  editName.value = s.name
}
async function saveRename(s) {
  if (editingSid.value !== s.sid) return   // 已保存过（enter 和 blur 会各触发一次）
  const name = editName.value.trim()
  editingSid.value = ''
  if (!name) return                        // 空名 = 放弃改名
  try {
    const resp = await fetch(`/api/sessions/${s.sid}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    s.name = name
  } catch (e) {
    error.value = e.message
  }
}
async function remove(s) {
  try {
    const resp = await fetch(`/api/sessions/${s.sid}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    sessions.value = sessions.value.filter((x) => x.sid !== s.sid)
    emit('deleted', s.sid)   // 让 App 知道：若删的是当前会话，要落到新会话
  } catch (e) {
    error.value = e.message
  }
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    @update:model-value="(v) => emit('update:modelValue', v)"
    title="会话"
    size="340px"
    class="session-drawer"
  >
    <div class="sp">
      <div v-if="loading" class="sp-state">加载中…</div>
      <div v-else-if="error" class="sp-state sp-error">加载失败：{{ error }}</div>
      <div v-else-if="sessions.length === 0" class="sp-state">
        还没有会话。发一条消息后，这里会出现历史会话。
      </div>
      <div v-else class="sp-list">
        <div
          v-for="s in sessions"
          :key="s.sid"
          class="sp-item"
          :class="{ active: s.sid === currentSid }"
          @click="pick(s)"
        >
          <el-icon class="sp-ic"><ChatDotRound /></el-icon>
          <div class="sp-main">
            <div class="sp-name">
              <el-input
                v-if="editingSid === s.sid"
                v-model="editName"
                size="small"
                @click.stop
                @keyup.enter="saveRename(s)"
                @blur="saveRename(s)"
              />
              <span v-else class="sp-name-text">{{ s.name }}</span>
            </div>
            <div class="sp-meta mono">{{ s.turns }} 轮 · {{ s.updated_at.slice(5) }}</div>
          </div>
          <div class="sp-actions" @click.stop>
            <el-button
              v-if="editingSid !== s.sid"
              size="small"
              text
              :icon="Edit"
              @click="startRename(s)"
            />
            <el-popconfirm
              title="删除这个会话？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              width="200"
              @confirm="remove(s)"
            >
              <template #reference>
                <el-button size="small" text :icon="Delete" class="sp-del" />
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped>
.sp { display: flex; flex-direction: column; gap: .6rem; }
.sp-state { color: var(--text-dim); padding: 1rem 0; font-size: .85rem; }
.sp-error { color: var(--error); }
.sp-list { display: flex; flex-direction: column; gap: .4rem; }
/* 每行一张浅色卡片：当前会话左边条亮主题蓝 + 淡蓝底，其余悬停才显边框 */
.sp-item {
  display: flex;
  align-items: center;
  gap: .55rem;
  padding: .55rem .7rem;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  border-radius: 0 4px 4px 0;
  background: rgba(15, 23, 32, .35);
  cursor: pointer;
  font-size: .82rem;
}
.sp-item:hover { border-color: var(--border); }
.sp-item.active {
  border-left-color: var(--user);
  background: color-mix(in srgb, var(--user) 10%, transparent);
}
.sp-ic { color: var(--text-dim); flex: none; font-size: .95rem; }
.sp-item.active .sp-ic { color: var(--user); }
.sp-main { flex: 1; min-width: 0; }
.sp-name { font-weight: 600; }
.sp-name-text {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sp-meta { color: var(--text-dim); font-size: .7rem; margin-top: .15rem; }
.sp-actions { display: flex; align-items: center; flex: none; }
.sp-del { color: var(--text-dim); }
.sp-del:hover { color: var(--error); }
</style>

<!-- 不 scope：el-drawer 会 teleport 到 body，scoped 选择器够不着它；和 TracePanel 同款磨砂玻璃。 -->
<style>
.session-drawer {
  background: rgba(22, 32, 43, .9) !important;
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.session-drawer .el-drawer__header {
  color: var(--text);
  margin-bottom: 0;
  padding: 1rem 1.2rem .7rem;
}
.session-drawer .el-drawer__body {
  padding: 0 1.2rem 1.4rem;
}
</style>
