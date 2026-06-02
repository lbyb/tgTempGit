/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue"
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface Window {
  getRowMainLink: (row: Element) => HTMLAnchorElement | null
  copyTextWithFallback: (text: string, okMsg: string) => Promise<void>
  copySelected: () => void
}
