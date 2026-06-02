import { createRouter, createWebHistory } from "vue-router"
import HomePage from "@/views/HomePage.vue"
import ProgressPage from "@/views/ProgressPage.vue"
import ResultPage from "@/views/ResultPage.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: HomePage,
    },
    {
      path: "/progress/:taskId",
      name: "progress",
      component: ProgressPage,
      props: true,
    },
    {
      path: "/result/:taskId",
      name: "result",
      component: ResultPage,
      props: true,
    },
  ],
})

export default router
