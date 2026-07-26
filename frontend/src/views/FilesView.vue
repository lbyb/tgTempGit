<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useFileApi } from "@/api/files"
import type { FileItem } from "@/types/file"
import FileTable from "@/components/FileTable.vue"
import UploadDialog from "@/components/UploadDialog.vue"
import RenameDialog from "@/components/RenameDialog.vue"

const { fetchFiles, deleteFile, deleteFiles, renameFile, error } = useFileApi()

const files = ref<FileItem[]>([])
const loading = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const showUpload = ref(false)
const renameTarget = ref<FileItem | null>(null)

async function loadFiles() {
  loading.value = true
  try {
    files.value = await fetchFiles()
  } catch {
    // error handled in composable
  } finally {
    loading.value = false
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB"
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB"
}

function formatTime(d: string): string {
  const date = new Date(d)
  return date.toLocaleString("zh-CN")
}

function toggleSelect(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleAll() {
  if (selectedIds.value.size === files.value.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(files.value.map(f => f.id))
  }
}

async function handleUploadDone(count: number) {
  showUpload.value = false
  await loadFiles()
}

async function handleDelete(id: string) {
  if (!confirm("确定删除该文件？")) return
  await deleteFile(id)
  selectedIds.value = new Set([...selectedIds.value].filter(x => x !== id))
  await loadFiles()
}

async function handleDeleteSelected() {
  if (selectedIds.value.size === 0) return
  if (!confirm(`确定删除选中的 ${selectedIds.value.size} 个文件？`)) return
  await deleteFiles([...selectedIds.value])
  selectedIds.value = new Set()
  await loadFiles()
}

async function handleDeleteAll() {
  if (files.value.length === 0) return
  if (!confirm(`确定删除全部 ${files.value.length} 个文件？`)) return
  await deleteFiles(files.value.map(f => f.id))
  selectedIds.value = new Set()
  await loadFiles()
}

function handleRenameClick(file: FileItem) {
  renameTarget.value = file
}

async function handleRenameSubmit(filename: string) {
  if (!renameTarget.value) return
  await renameFile(renameTarget.value.id, filename)
  renameTarget.value = null
  await loadFiles()
}

function downloadUrl(file: FileItem): string {
  const url = new URL(`/api/files/${file.id}`, window.location.origin)
  const token = new URLSearchParams(window.location.search).get("token")
  if (token) url.searchParams.set("token", token)
  return url.toString()
}

onMounted(loadFiles)
</script>

<template>
  <div class="app-container">
    <header class="app-header">
      <h1>cfCloudFile</h1>
    </header>

    <div v-if="error" class="error-bar">{{ error }}</div>

    <div class="toolbar">
      <button class="btn btn-primary" @click="showUpload = true">+ 上传文件</button>
      <button
        class="btn btn-danger"
        :disabled="selectedIds.size === 0"
        @click="handleDeleteSelected"
      >
        删除选中 ({{ selectedIds.size }})
      </button>
      <button
        class="btn btn-danger-outline"
        :disabled="files.length === 0"
        @click="handleDeleteAll"
      >
        删除全部
      </button>
      <span class="file-count">共 {{ files.length }} 个文件</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <FileTable
      v-else-if="files.length > 0"
      :files="files"
      :selected-ids="selectedIds"
      :format-size="formatSize"
      :format-time="formatTime"
      :download-url="downloadUrl"
      @toggle-select="toggleSelect"
      @toggle-all="toggleAll"
      @delete="handleDelete"
      @rename="handleRenameClick"
    />

    <p v-else class="empty">暂无文件，请上传</p>

    <UploadDialog
      v-if="showUpload"
      @done="handleUploadDone"
      @close="showUpload = false"
    />

    <RenameDialog
      v-if="renameTarget"
      :filename="renameTarget.original_filename"
      @confirm="handleRenameSubmit"
      @close="renameTarget = null"
    />
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f5f7fa;
  color: #333;
}
</style>

<style scoped>
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.app-header {
  margin-bottom: 20px;
}

.app-header h1 {
  font-size: 24px;
  font-weight: 700;
  color: #1a73e8;
}

.error-bar {
  background: #fdecea;
  color: #b71c1c;
  padding: 10px 16px;
  border-radius: 6px;
  margin-bottom: 16px;
  font-size: 14px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.file-count {
  margin-left: auto;
  color: #888;
  font-size: 13px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary {
  background: #1a73e8;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #1557b0;
}

.btn-danger {
  background: #d93025;
  color: #fff;
}

.btn-danger:hover:not(:disabled) {
  background: #b71c1c;
}

.btn-danger-outline {
  background: transparent;
  color: #d93025;
  border: 1px solid #d93025;
}

.btn-danger-outline:hover:not(:disabled) {
  background: #fdecea;
}

.loading,
.empty {
  text-align: center;
  color: #999;
  padding: 60px 0;
  font-size: 15px;
}
</style>
