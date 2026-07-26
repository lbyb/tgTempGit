export interface FileItem {
  id: string
  filename: string
  original_filename: string
  size: number
  content_type: string | null
  created_at: string
  updated_at: string
}

export interface BatchDeleteRequest {
  ids: string[]
}

export interface RenameRequest {
  filename: string
}

export interface UploadTask {
  id: number
  file: File
  progress: number
  status: "pending" | "uploading" | "done" | "error"
  error?: string
  result?: FileItem
}
