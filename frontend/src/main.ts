import { createApp } from "vue"
import { createRouter, createWebHistory } from "vue-router"
import App from "./App.vue"

const routes = [
  {
    path: "/",
    name: "home",
    component: () => import("@/views/FilesView.vue"),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

createApp(App).use(router).mount("#app")
