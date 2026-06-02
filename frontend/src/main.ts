import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"

try {
  const app = createApp(App)
  app.config.errorHandler = (err) => {
    const el = document.getElementById("app")
    if (el) {
      el.innerHTML = `<div style="color:red;padding:20px;font-family:monospace;">
        <h3>应用运行时错误</h3>
        <pre>${String(err)}</pre>
      </div>`
    }
  }
  app.use(router)
  app.mount("#app")
} catch (err) {
  const el = document.getElementById("app")
  if (el) {
    el.innerHTML = `<div style="color:red;padding:20px;font-family:monospace;">
      <h3>应用初始化失败</h3>
      <pre>${String(err)}</pre>
    </div>`
  }
}
