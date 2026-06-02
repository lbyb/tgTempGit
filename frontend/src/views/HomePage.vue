<script setup lang="ts">
import { ref } from "vue"
import { useRouter } from "vue-router"
import { createSearch } from "@/api"

const router = useRouter()

const seriesUrl = ref("")
const isbns = ref("9787101066890,9787807454908")
const loading = ref(false)
const error = ref("")

async function onSubmit(): Promise<void> {
  error.value = ""
  loading.value = true
  try {
    const res = await createSearch({
      series_url: seriesUrl.value || null,
      isbns: isbns.value || null,
    })
    if (res.task_id) {
      if (res.cached) {
        router.push({ name: "result", params: { taskId: res.task_id } })
      } else {
        router.push({ name: "progress", params: { taskId: res.task_id } })
      }
    } else if (res.html) {
      router.push({ name: "result", params: { taskId: "isbn" }, query: { html: res.html } })
    } else {
      error.value = "请输入丛书URL或ISBN"
    }
  } catch (e) {
    error.value = "请求失败：" + (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="wrap">
    <div class="topbar"><h2>豆瓣丛书 → AA 合并搜索</h2></div>

    <form class="form" @submit.prevent="onSubmit">
      <div>
        <div class="label">方式一：豆瓣丛书URL（支持逗号分隔多个）</div>
        <input
          v-model="seriesUrl"
          class="input"
          placeholder="如：https://book.douban.com/series/1300,https://book.douban.com/series/1301"
          :disabled="loading"
        />
        <div class="help">支持输入多个series URL，用逗号分隔。处理多个series时每个之间会延时1分钟。</div>

        <div class="sec label">方式二：手动输入 ISBN（逗号或空格分隔）</div>
        <input
          v-model="isbns"
          class="input"
          placeholder="如：9787101066890,9787807454908"
          :disabled="loading"
        />
        <div class="help">若同时填写丛书URL与ISBN，则优先使用丛书URL。</div>
      </div>
      <button class="btn" type="submit" :disabled="loading">
        {{ loading ? "提交中..." : "合并搜索结果" }}
      </button>
    </form>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="notice">
      <strong>注意：</strong>处理豆瓣丛书需要时间，提交后页面会显示进度，请耐心等待。
    </div>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px;
}
.topbar {
  position: sticky;
  top: 0;
  background: #fff;
  padding: 12px 8px;
  border-bottom: 1px solid #eee;
  z-index: 999;
}
.form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: center;
}
.input {
  padding: 8px 10px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  width: 100%;
  box-sizing: border-box;
}
.btn {
  padding: 8px 14px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  background: #f6f8fa;
  cursor: pointer;
}
.btn:hover {
  background: #eef1f4;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.help {
  font-size: 12px;
  color: #666;
  margin-top: 8px;
}
.sec {
  margin-top: 18px;
}
.label {
  font-weight: 600;
  margin-bottom: 6px;
}
.notice {
  background: #fff3cd;
  border: 1px solid #ffeb3b;
  padding: 10px;
  border-radius: 5px;
  margin-top: 10px;
}
.error {
  color: red;
  margin-top: 10px;
}
</style>
