import { onlineManager } from '@tanstack/vue-query'
import { readonly, ref } from 'vue'

const online = ref(onlineManager.isOnline())

onlineManager.subscribe((isOnline) => {
  online.value = isOnline
})

export const mobileOnline = readonly(online)

export function getOnlineRefetchInterval(
  intervalMilliseconds: number,
): number | false {
  return online.value ? intervalMilliseconds : false
}

export function canRunBackgroundFetch(): boolean {
  return online.value
}
