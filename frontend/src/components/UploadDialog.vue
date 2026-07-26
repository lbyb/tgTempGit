<script setup lang="ts">
import { ref, computed, nextTick, type Ref } from "vue"
import { useFileApi } from "@/api/files"
import type { UploadTask } from "@/types/file"

const emit = defineEmits<{
  done: [results: number]
  close: []
}>()

const { uploadFileWithProgress } = useFileApi()

const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const uploading = ref(false)
const tasks: Ref<UploadTask[]> = ref([])
let nextId = 1

const MAX_SIZE = 500 * 1024 * 1024

function addFiles(fileList: FileList | null) {
  if (!fileList) return
  for (let i = 0; i < fileList.length; i++) {
    const f = fileList[i]
    if (f.size > MAX_SIZE) {
      tasks.value.push({
        id: nextId++,
        file: f,
        progress: 0,
        status: "error",
        error: `超过 500MB 限制`,
      })
    } else {
      tasks.value.push({
        id: nextId++,
        file: f,
        progress: 0,
        status: "pending",
      })
    }
  }
}

function handleDrop(e: DragEvent) {
  dragging.value = false
  addFiles(e.dataTransfer?.files ?? null)
}

function handleChange() {
  addFiles(fileInput.value?.files ?? null)
  fileInput.value!.value = ""
}

function removeTask(id: number) {
  tasks.value = tasks.value.filter(t => t.status !== "uploading" || t.id !== id)
  if (!uploading.value) {
    tasks.value = tasks.value.filter(t => t.id !== id)
  }
}

const canUpload = computed(() =>
  tasks.value.some(t => t.status === "pending") && !uploading.value,
)

const hasActive = computed(() =>
  tasks.value.some(t => t.status === "pending" || t.status === "uploading"),
)

const doneCount = computed(() => tasks.value.filter(t => t.status === "done").length)
const errorCount = computed(() => tasks.value.filter(t => t.status === "error").length)

async function startUpload() {
  uploading.value = true
  const pending = tasks.value.filter(t => t.status === "pending")

  for (const task of pending) {
    task.status = "uploading"
    task.progress = 0
    try {
      const result = await uploadFileWithProgress(task.file, (pct) => {
        task.progress = pct
      })
      task.status = "done"
      task.progress = 100
      task.result = result
    } catch (e: unknown) {
      task.status = "error"
      task.error = e instanceof Error ? e.message : "上传失败"
    }
  }

  uploading.value = false
  const ok = tasks.value.filter(t => t.status === "done").length
  if (ok > 0) emit("done", ok)
}

function handleClose() {
  if (uploading.value) return
  emit("close")
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB"
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB"
}

function clearDone() {
  tasks.value = tasks.value.filter(t => t.status !== "done")
  const allDone = tasks.value.length === 0 || tasks.value.every(t => t.status === "error")
  if (allDone && doneCount.value === 0 && !uploading.value) {
    emit("close")
  }
}
</script>

<template>
  <div class="overlay" @click.self="handleClose">
    <div class="dialog">
      <h3>上传文件</h3>
      <p class="hint">支持多文件，单文件最大 500MB</p>

      <div
        class="drop-zone"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="handleDrop"
        @click="fileInput?.click()"
      >
        <p v-if="tasks.length === 0">拖拽文件到此处，或点击选择文件</p>
        <p v-else>继续拖拽或点击添加更多文件</p>
      </div>

      <input
        ref="fileInput"
        type="file"
        multiple
        style="display:none"
        @change="handleChange"
      />

      <!-- 上传进度列表 -->
      <div v-if="tasks.length > 0" class="task-list">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-item"
          :class="`status-${task.status}`"
        >
          <div class="task-info">
            <span class="task-name">{{ task.file.name }}</span>
            <span class="task-size">{{ formatSize(task.file.size) }}</span>
          </div>

          <!-- pending -->
          <div v-if="task.status === 'pending'" class="task-bar-wrap">
            <div class="task-bar pending-bar" />
            <span class="task-label">等待上传</span>
          </div>

          <!-- uploading -->
          <div v-else-if="task.status === 'uploading'" class="task-bar-wrap">
            <div class="task-bar">
              <div class="task-bar-fill" :style="{ width: task.progress + '%' }" />
            </div>
            <span class="task-label">{{ task.progress }}%</span>
          </div>

          <!-- done -->
          <div v-else-if="task.status === 'done'" class="task-bar-wrap">
            <div class="task-bar">
              <div class="task-bar-fill done-fill" style="width:100%" />
            </div>
            <span class="task-label task-ok">完成</span>
          </div>

          <!-- error -->
          <div v-else-if="task.status === 'error'" class="task-err">
            {{ task.error || "失败" }}
          </div>
        </div>
      </div>

      <div class="btns">
        <button
          v-if="!uploading"
          class="btn btn-clear"
          :disabled="doneCount === 0"
          @click="clearDone"
        >清除完成</button>
        <span class="summary" v-if="doneCount > 0 || errorCount > 0">
          成功 {{ doneCount }} / 失败 {{ errorCount }}
        </span>
        <button class="btn btn-cancel" :disabled="uploading" @click="handleClose">
          {{ uploading ? "上传中..." : "关闭" }}
        </button>
        <button
          class="btn btn-submit"
          :disabled="!canUpload"
          @click="startUpload"
        >
          开始上传
        </button>
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
  width: 520px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
}
h3 { font-size: 18px; margin-bottom: 4px; }
.hint { color: #888; font-size: 13px; margin-bottom: 16px; }
.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 28px 20px;
  text-align: center;
  cursor: pointer;
  color: #888;
  transition: border-color 0.15s;
  flex-shrink: 0;
}
.drop-zone:hover, .drop-zone.dragging {
  border-color: #1a73e8;
  background: #e8f0fe;
}

.task-list {
  margin-top: 16px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
.task-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.task-item:last-child { border-bottom: none; }
.task-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.task-name {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}
.task-size { font-size: 12px; color: #888; }
.task-bar-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.task-bar {
  flex: 1;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
}
.task-bar-fill {
  height: 100%;
  background: #1a73e8;
  border-radius: 4px;
  transition: width 0.2s;
}
.done-fill { background: #34a853; }
.pending-bar { width: 100%; background: #e0e0e0; }
.task-label { font-size: 12px; color: #666; white-space: nowrap; }
.task-ok { color: #34a853; }
.task-err { font-size: 12px; color: #d93025; }

.btns {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 20px;
  flex-shrink: 0;
}
.summary { font-size: 13px; color: #666; margin-right: auto; }
.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-cancel { background: #f1f3f4; color: #555; }
.btn-clear { background: #f1f3f4; color: #555; }
.btn-submit { background: #1a73e8; color: #fff; }
.btn-submit:hover:not(:disabled) { background: #1557b0; }
</style>
