<script setup>
// 输入框：回车或点按钮发送；生成中禁用
import { ref } from 'vue'

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
    <input
      v-model="text"
      placeholder="输入任务，例如：帮我计算 2+3 的结果"
      :disabled="disabled"
      @keyup.enter="submit"
    >
    <button :disabled="disabled" @click="submit">发送</button>
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
.input-bar input {
  flex: 1;
  padding: .6rem .9rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--bg);
  color: var(--text);
  font-size: .95rem;
}
.input-bar input::placeholder { color: var(--text-dim); }
.input-bar input:focus {
  outline: none;
  border-color: var(--user);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--user) 18%, transparent);
}
.input-bar button {
  padding: .6rem 1.3rem;
  border: 1px solid var(--user);
  border-radius: 4px;
  background: transparent;
  color: var(--user);
  font-size: .95rem;
  cursor: pointer;
}
.input-bar button:not(:disabled):hover { background: var(--user); color: var(--bg); }
.input-bar button:disabled,
.input-bar input:disabled { opacity: .45; cursor: not-allowed; }
</style>
