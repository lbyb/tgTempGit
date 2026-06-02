<script setup lang="ts">
import { onErrorCaptured, ref } from "vue"

const error = ref("")

onErrorCaptured((err) => {
  error.value = "页面加载异常: " + String(err)
  return false
})
</script>

<template>
  <div v-if="error" style="color:red;padding:20px;font-family:monospace;">
    {{ error }}
  </div>
  <router-view v-else />
</template>
