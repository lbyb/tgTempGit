<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue"
import { useRouter } from "vue-router"
import { getTaskStatus } from "@/api"

const props = defineProps<{ taskId: string }>()
const router = useRouter()

const status = ref("pending")
const currentSeries = ref(0)
const totalSeries = ref(0)
const currentUrl = ref("")
const errorMsg = ref("")
let timer: ReturnType<typeof setInterval> | null = null

async function checkStatus(): Promise<void> {
  try {
    const data = await getTaskStatus(props.taskId)
    status.value = data.status
    currentSeries.value = data.current_series
    totalSeries.value = data.total_series
    currentUrl.value = data.current_url

    if (data.error) {
      errorMsg.value = data.error
      if (timer) clearInterval(timer)
      return
    }

    if (data.status === "completed") {
      if (timer) clearInterval(timer)
      router.push({ name: "result", params: { taskId: props.taskId } })
    } else if (data.status === "failed") {
      if (timer) clearInterval(timer)
    }
  } catch (e) {
    errorMsg.value = "状态检查失败：" + (e as Error).message
    if (timer) clearInterval(timer)
  }
}

onMounted(() => {
  checkStatus()
  timer = setInterval(checkStatus, 2000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="container">
    <h1>正在处理豆瓣丛书...</h1>
    <div class="progress">
      <div class="status">
        <template v-if="status === 'pending'">
          <div class="spinner"></div>
          <p>等待处理...</p>
        </template>
        <template v-else-if="status === 'processing'">
          <div class="spinner"></div>
          <p>正在处理第 {{ currentSeries }}/{{ totalSeries }} 个系列...</p>
          <p>当前URL: {{ currentUrl }}</p>
        </template>
        <template v-else-if="status === 'completed'">
          <p class="success">处理完成！正在跳转到结果页面...</p>
        </template>
        <template v-else-if="status === 'failed'">
          <p class="error-text">处理失败: {{ errorMsg }}</p>
        </template>
        <template v-else>
          <p class="error-text">任务未找到</p>
        </template>
      </div>
    </div>
    <p class="hint">提示：处理多个系列时，每个系列之间会延时1分钟，请耐心等待。</p>
  </div>
</template>

<style scoped>
.container {
  font-family: Arial, sans-serif;
  max-width: 800px;
  margin: 50px auto;
  padding: 20px;
}
.progress {
  background: #f0f0f0;
  border-radius: 5px;
  padding: 20px;
  margin: 20px 0;
}
.status {
  font-size: 18px;
  margin: 10px 0;
}
.spinner {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  vertical-align: middle;
  margin-right: 8px;
}
@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
.error-text {
  color: red;
  font-weight: bold;
}
.success {
  color: green;
  font-weight: bold;
}
.hint {
  color: #666;
}
</style>
