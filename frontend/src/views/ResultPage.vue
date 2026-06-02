<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getTaskResult, getHistory, clearHistory, type HistoryEntry } from "@/api"

const route = useRoute()
const router = useRouter()
const props = defineProps<{ taskId: string }>()

const htmlContent = ref("")
const error = ref("")
const loading = ref(true)
const history = ref<HistoryEntry[]>([])
const selectedTaskId = ref(props.taskId)

onMounted(async () => {
  const queryHtml = route.query.html as string | undefined
  if (queryHtml) {
    htmlContent.value = queryHtml
    loading.value = false
    await loadHistory()
    return
  }

  await Promise.all([loadHistory(), loadResult(props.taskId)])
  loading.value = false
  selectedTaskId.value = props.taskId
})

async function loadHistory(): Promise<void> {
  try {
    history.value = await getHistory()
  } catch {
    history.value = []
  }
}

async function loadResult(taskId: string): Promise<void> {
  loading.value = true
  try {
    const data = await getTaskResult(taskId)
    if (data.html) {
      htmlContent.value = data.html
      error.value = ""
    } else if (data.error) {
      error.value = data.error
    } else if (data.status) {
      error.value = "任务仍在处理中，请稍后刷新页面..."
    }
  } catch (e) {
    error.value = "获取结果失败：" + (e as Error).message
  } finally {
    loading.value = false
  }
}

function onSwitchHistory(): void {
  if (selectedTaskId.value) {
    router.replace({ name: "result", params: { taskId: selectedTaskId.value } })
    loadResult(selectedTaskId.value)
  }
}

async function onClearHistory(): Promise<void> {
  if (!confirm("确定要清除所有历史记录吗？此操作不可恢复。")) return
  try {
    await clearHistory()
    history.value = []
    htmlContent.value = ""
    selectedTaskId.value = ""
    router.push({ name: "home" })
  } catch (e) {
    error.value = "清除失败：" + (e as Error).message
  }
}

function formatLabel(entry: HistoryEntry): string {
  const name = entry.display_name.length > 50
    ? entry.display_name.slice(0, 50) + "..."
    : entry.display_name
  return `[${entry.status === "completed" ? "完成" : "失败"}] ${name} (${entry.total_books}本)`
}
</script>

<template>
  <div v-if="loading" class="loading">
    <div class="spinner"></div>
    <p>加载结果中...</p>
  </div>

  <template v-else>
    <div class="history-toolbar" v-if="history.length > 0">
      <select v-model="selectedTaskId" @change="onSwitchHistory" class="history-select">
        <option v-for="entry in history" :key="entry.task_id" :value="entry.task_id">
          {{ formatLabel(entry) }}
        </option>
      </select>
      <button class="clear-btn" @click="onClearHistory">清除历史</button>
    </div>

    <div v-if="error" class="error">
      <p>{{ error }}</p>
    </div>
    <div v-else-if="htmlContent" v-html="htmlContent"></div>
    <div v-else class="error">
      <p>无结果数据</p>
    </div>
  </template>
</template>

<style scoped>
.loading {
  text-align: center;
  padding: 100px 20px;
}
.spinner {
  display: inline-block;
  width: 30px;
  height: 30px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.error {
  color: red;
  text-align: center;
  padding: 50px 20px;
}
.history-toolbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  background: #fff;
  padding: 10px;
  border-bottom: 1px solid #eee;
}
.history-select {
  padding: 8px 12px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  font-size: 14px;
  background: #f6f8fa;
  cursor: pointer;
  max-width: 500px;
}
.history-select:hover {
  background: #eef1f4;
}
.clear-btn {
  padding: 8px 14px;
  border: 1px solid #e74c3c;
  border-radius: 8px;
  background: #fff;
  color: #e74c3c;
  cursor: pointer;
  font-size: 14px;
}
.clear-btn:hover {
  background: #e74c3c;
  color: #fff;
}
</style>
