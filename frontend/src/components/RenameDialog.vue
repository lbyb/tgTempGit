<script setup lang="ts">
import { ref, onMounted } from "vue"

interface Props {
  filename: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  confirm: [filename: string]
  close: []
}>()

const input = ref<HTMLInputElement | null>(null)
const name = ref(props.filename)
const error = ref("")

function submit() {
  const v = name.value.trim()
  if (!v) {
    error.value = "文件名不能为空"
    return
  }
  emit("confirm", v)
}

onMounted(() => {
  input.value?.focus()
  input.value?.select()
})
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="dialog">
      <h3>重命名</h3>
      <input
        ref="input"
        v-model="name"
        class="input"
        @keyup.enter="submit"
        @keyup.esc="$emit('close')"
      />
      <p v-if="error" class="err">{{ error }}</p>
      <div class="btns">
        <button class="btn btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn btn-submit" @click="submit">确认</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.dialog {
  background: #fff;
  border-radius: 10px;
  padding: 28px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
}

h3 {
  font-size: 18px;
  margin-bottom: 14px;
}

.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
}

.input:focus {
  border-color: #1a73e8;
}

.err {
  color: #d93025;
  font-size: 13px;
  margin-top: 8px;
}

.btns {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-cancel {
  background: #f1f3f4;
  color: #555;
}

.btn-submit {
  background: #1a73e8;
  color: #fff;
}

.btn-submit:hover {
  background: #1557b0;
}
</style>
