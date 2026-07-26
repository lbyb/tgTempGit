<script setup lang="ts">
import type { FileItem } from "@/types/file"

interface Props {
  files: FileItem[]
  selectedIds: Set<string>
  formatSize: (bytes: number) => string
  formatTime: (d: string) => string
  downloadUrl: (file: FileItem) => string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  toggleSelect: [id: string]
  toggleAll: []
  delete: [id: string]
  rename: [file: FileItem]
}>()

const allSelected = (): boolean => props.files.length > 0 && props.selectedIds.size === props.files.length
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="col-cb">
            <input
              type="checkbox"
              :checked="allSelected()"
              @change="emit('toggleAll')"
            />
          </th>
          <th class="col-name">文件名</th>
          <th class="col-size">大小</th>
          <th class="col-time">创建时间</th>
          <th class="col-actions">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in files" :key="f.id">
          <td class="col-cb">
            <input
              type="checkbox"
              :checked="selectedIds.has(f.id)"
              @change="emit('toggleSelect', f.id)"
            />
          </td>
          <td class="col-name">
            <a :href="downloadUrl(f)" class="file-link">{{ f.original_filename }}</a>
          </td>
          <td class="col-size">{{ formatSize(f.size) }}</td>
          <td class="col-time">{{ formatTime(f.created_at) }}</td>
          <td class="col-actions">
            <button class="act-btn" @click="emit('rename', f)">改名</button>
            <a class="act-btn" :href="downloadUrl(f)">下载</a>
            <button class="act-btn act-del" @click="emit('delete', f.id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-size: 14px;
  white-space: nowrap;
}

th {
  background: #f9fafb;
  font-weight: 600;
  color: #555;
}

.col-cb {
  width: 40px;
}

.col-name {
  min-width: 200px;
}

.col-size {
  width: 100px;
}

.col-time {
  width: 180px;
}

.col-actions {
  width: 160px;
}

.file-link {
  color: #1a73e8;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 400px;
}

.file-link:hover {
  text-decoration: underline;
}

.act-btn {
  background: none;
  border: none;
  color: #1a73e8;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 8px;
  border-radius: 4px;
  text-decoration: none;
  display: inline-block;
}

.act-btn:hover {
  background: #e8f0fe;
}

.act-del {
  color: #d93025;
}

.act-del:hover {
  background: #fdecea;
}

input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
</style>
