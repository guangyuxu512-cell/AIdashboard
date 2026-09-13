import { readonly, ref } from 'vue'
import type { Router } from 'vue-router'

const updateRequired = ref(false)
export const clientUpdateRequired = readonly(updateRequired)

export function isResourceLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /Failed to fetch dynamically imported module|Importing a module script failed|error loading dynamically imported module|Unable to preload CSS|Loading chunk .+ failed/i.test(
    message,
  )
}

export function installClientUpdateDetection(router: Router): () => void {
  const markUnavailable = () => {
    updateRequired.value = true
  }
  const removeRouterHandler = router.onError((error) => {
    if (isResourceLoadError(error)) markUnavailable()
  })
  // Keep the import rejection: Vue Router must abort navigation and preserve
  // the currently mounted page (and its unsaved form), not mount undefined.
  window.addEventListener('vite:preloadError', markUnavailable)
  return () => {
    removeRouterHandler()
    window.removeEventListener('vite:preloadError', markUnavailable)
  }
}
