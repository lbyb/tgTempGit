---
name: vue3
description: Vue 3 Composition API best practices. Use when building Vue 3 applications with TypeScript, Vite, Pinia state management, Vue Router, or when writing components with <script setup> syntax.
---

# Vue 3 最佳实践

## 项目创建

使用 Vite 创建项目：

```bash
npm create vite@latest my-app -- --template vue-ts
```

## 组件规范

### 始终使用 `<script setup>` + TypeScript

```vue
<script setup lang="ts">
import { ref, computed, onMounted } from "vue"

interface Props {
  title: string
  count?: number
}

const props = withDefaults(defineProps<Props>(), {
  count: 0,
})

const emit = defineEmits<{
  update: [value: number]
  close: []
}>()

const localCount = ref(props.count)
const doubled = computed(() => localCount.value * 2)

function increment(): void {
  localCount.value++
  emit("update", localCount.value)
}

onMounted(() => {
  console.log("component mounted")
})
</script>

<template>
  <div>
    <h2>{{ title }}</h2>
    <p>Count: {{ localCount }} (doubled: {{ doubled }})</p>
    <button @click="increment">+1</button>
  </div>
</template>

<style scoped>
h2 {
  color: #42b883;
}
</style>
```

## Composables（组合函数）

```typescript
// composables/useCounter.ts
import { ref, computed, type Ref, type ComputedRef } from "vue"

export function useCounter(initial: number = 0): {
  count: Ref<number>
  doubled: ComputedRef<number>
  increment: () => void
  decrement: () => void
} {
  const count = ref(initial)
  const doubled = computed(() => count.value * 2)

  function increment(): void {
    count.value++
  }
  function decrement(): void {
    count.value--
  }

  return { count, doubled, increment, decrement }
}
```

在组件中使用：

```vue
<script setup lang="ts">
import { useCounter } from "@/composables/useCounter"

const { count, doubled, increment } = useCounter(5)
</script>
```

## Pinia 状态管理

```typescript
// stores/user.ts
import { defineStore } from "pinia"
import { ref, computed } from "vue"

interface User {
  id: number
  name: string
  email: string
}

export const useUserStore = defineStore("user", () => {
  const user = ref<User | null>(null)
  const isLoggedIn = computed(() => user.value !== null)

  async function login(email: string, password: string): Promise<void> {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    user.value = await response.json()
  }

  function logout(): void {
    user.value = null
  }

  return { user, isLoggedIn, login, logout }
})
```

## Vue Router

```typescript
// router/index.ts
import { createRouter, createWebHistory } from "vue-router"

const routes = [
  {
    path: "/",
    name: "home",
    component: () => import("@/views/HomeView.vue"),
  },
  {
    path: "/users/:id",
    name: "user-detail",
    component: () => import("@/views/UserDetail.vue"),
    props: true,
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
```

## Vite 配置

```typescript
// vite.config.ts
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { fileURLToPath } from "node:url"

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})
```

## 测试（vitest）

```typescript
// Counter.test.ts
import { mount } from "@vue/test-utils"
import { describe, it, expect } from "vitest"
import Counter from "@/components/Counter.vue"

describe("Counter", () => {
  it("increments count on button click", async () => {
    const wrapper = mount(Counter, { props: { title: "Test", count: 0 } })
    await wrapper.find("button").trigger("click")
    expect(wrapper.text()).toContain("Count: 1")
  })
})
```

## 常用组合

### watchEffect 自动追踪

```typescript
import { ref, watchEffect } from "vue"

const userId = ref(1)
const userData = ref<User | null>(null)

watchEffect(async () => {
  // 自动追踪 userId，变化时重新请求
  userData.value = await fetchUser(userId.value)
})
```

### Template Refs

```vue
<script setup lang="ts">
import { ref, onMounted, type Ref } from "vue"

const inputRef: Ref<HTMLInputElement | null> = ref(null)

onMounted(() => {
  inputRef.value?.focus()
})
</script>

<template>
  <input ref="inputRef" />
</template>
```
