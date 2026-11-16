import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'

import { isAiGenerationVisualMockEnabled } from './visual-mock-gate'
import { useAiGenerationStore } from './useAiGenerationStore'

const visualMockLoader = import.meta.env.DEV
  ? () => import('./load-visual-mock')
  : null

export function useAiGenerationRuntime() {
  const route = useRoute()
  const generationStore = useAiGenerationStore()
  const visualMockEnabled = computed(() =>
    isAiGenerationVisualMockEnabled(
      import.meta.env.DEV,
      route.query.visualMock,
    ),
  )

  watch(
    visualMockEnabled,
    async (enabled) => {
      if (!enabled) {
        generationStore.setVisualMockActive(false)
        return
      }
      if (generationStore.visualMockLoaded) {
        generationStore.setVisualMockActive(true)
        return
      }
      if (!visualMockLoader) return
      const { loadAiGenerationVisualMock } = await visualMockLoader()
      if (visualMockEnabled.value) {
        generationStore.initializeVisualMock(loadAiGenerationVisualMock())
      }
    },
    { immediate: true },
  )

  return { generationStore, visualMockEnabled }
}
