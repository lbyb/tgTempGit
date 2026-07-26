import { computed } from "vue"
import { useRoute } from "vue-router"

export function useToken() {
  const route = useRoute()
  const token = computed(() => {
    const t = route.query.token
    return typeof t === "string" ? t : ""
  })

  function getUrl(path: string): string {
    const url = new URL(path, window.location.origin)
    if (token.value) {
      url.searchParams.set("token", token.value)
    }
    return url.toString()
  }

  return { token, getUrl }
}
