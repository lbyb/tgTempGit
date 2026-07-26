import type { FileItem, UploadTask } from "@/types/file"
import { useToken } from "@/composables/useToken"
import { ref } from "vue"

export function useFileApi() {
  const { getUrl, token } = useToken()
  const error = ref("")

  function tokenParam(): string {
    return token.value ? `?token=${encodeURIComponent(token.value)}` : ""
  }

  async function fetchFiles(): Promise<FileItem[]> {
    error.value = ""
    const res = await fetch(getUrl("/api/files"))
    if (!res.ok) {
      if (res.status === 403) {
        error.value = "token 无效，请通过正确的 URL 访问"
      } else {
        error.value = `请求失败: ${res.status}`
      }
      throw new Error(error.value)
    }
    return res.json()
  }

  function uploadFileWithProgress(
    file: File,
    onProgress: (pct: number) => void,
  ): Promise<FileItem> {
    return new Promise((resolve, reject) => {
      const form = new FormData()
      form.append("file", file)

      const xhr = new XMLHttpRequest()
      xhr.open("POST", getUrl("/api/files/upload"))

      xhr.upload.onprogress = (e: ProgressEvent) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100))
        }
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText))
        } else {
          try {
            const data = JSON.parse(xhr.responseText)
            reject(new Error(data.detail || `上传失败 (${xhr.status})`))
          } catch {
            reject(new Error(`上传失败 (${xhr.status})`))
          }
        }
      }

      xhr.onerror = () => reject(new Error("网络错误，上传失败"))
      xhr.send(form)
    })
  }

  async function uploadFile(file: File): Promise<FileItem> {
    error.value = ""
    const form = new FormData()
    form.append("file", file)
    const res = await fetch(getUrl("/api/files/upload"), {
      method: "POST",
      body: form,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({ detail: "上传失败" }))
      error.value = data.detail || `上传失败 (${res.status})`
      throw new Error(error.value)
    }
    return res.json()
  }

  async function deleteFile(id: string): Promise<void> {
    error.value = ""
    const res = await fetch(getUrl(`/api/files/${id}`), { method: "DELETE" })
    if (!res.ok) throw new Error("删除失败")
  }

  async function deleteFiles(ids: string[]): Promise<void> {
    error.value = ""
    const res = await fetch(getUrl("/api/files"), {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    })
    if (!res.ok) throw new Error("批量删除失败")
  }

  async function renameFile(id: string, filename: string): Promise<FileItem> {
    error.value = ""
    const res = await fetch(getUrl(`/api/files/${id}`), {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    })
    if (!res.ok) throw new Error("重命名失败")
    return res.json()
  }

  return { fetchFiles, uploadFile, uploadFileWithProgress, deleteFile, deleteFiles, renameFile, error }
}
