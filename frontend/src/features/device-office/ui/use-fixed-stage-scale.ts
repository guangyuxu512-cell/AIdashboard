import { onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

import { OFFICE_DESIGN_CANVAS } from '../model/office-layout'

export function useFixedStageScale(host: Ref<HTMLElement | null>) {
  const scale = ref(1)
  let observer: ResizeObserver | null = null

  function updateScale(): void {
    if (!host.value) return
    const { clientWidth, clientHeight } = host.value
    scale.value = Math.min(
      clientWidth / OFFICE_DESIGN_CANVAS.width,
      clientHeight / OFFICE_DESIGN_CANVAS.height,
    )
  }

  onMounted(() => {
    updateScale()
    observer = new ResizeObserver(updateScale)
    if (host.value) observer.observe(host.value)
  })

  onBeforeUnmount(() => observer?.disconnect())

  return { scale }
}
