<script setup>
// 输入框：回车或点按钮发送；生成中禁用。组件用 Element Plus（el-input + el-button）。
import { ref } from 'vue'
import { Promotion } from '@element-plus/icons-vue'

defineProps({
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['send'])
const text = ref('')

function submit() {
  const t = text.value.trim()
  if (!t) return
  emit('send', t)
  text.value = ''
}
</script>

<template>
  <div class="input-bar">
    <el-input
      v-model="text"
      placeholder="输入任务，例如：帮我计算 2+3 的结果"
      :disabled="disabled"
      size="large"
      @keyup.enter="submit"
    />
    <el-button
      type="primary"
      size="large"
      :icon="Promotion"
      :disabled="disabled"
      @click="submit"
    >发送</el-button>
  </div>
</template>

<style scoped>
.input-bar {
  display: flex;
  gap: .6rem;
  padding: .9rem 1.1rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
}
/* el-input 的边框是 box-shadow 画的（EP 惯例），用 :deep 覆盖成终端风 */
.input-bar :deep(.el-input__wrapper) {
  background: var(--bg);
  box-shadow: 0 0 0 1px var(--border) inset;
}
.input-bar :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--user) inset,
              0 0 0 3px color-mix(in srgb, var(--user) 15%, transparent);
}
.input-bar :deep(.el-input__inner) { color: var(--text); }
.input-bar :deep(.el-input__inner::placeholder) { color: var(--text-dim); }
</style>
