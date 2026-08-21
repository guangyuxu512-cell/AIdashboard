import { computed, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'

import {
  useCreateNotificationChannelMutation,
  useNotificationChannelsQuery,
  useTestNotificationChannelMutation,
  useUpdateNotificationChannelMutation,
  type NotificationChannelSaveInput,
} from '@/entities/notification-channel'
import { getErrorMessage } from '@/shared/api'

export function useNotificationSettings() {
  const message = useMessage()
  const channelsQuery = useNotificationChannelsQuery()
  const createMutation = useCreateNotificationChannelMutation()
  const updateMutation = useUpdateNotificationChannelMutation()
  const testMutation = useTestNotificationChannelMutation()
  const selectedChannelId = ref<string | null>(null)
  const creating = ref(false)

  const channels = computed(() => channelsQuery.data.value ?? [])
  const selectedChannel = computed(
    () =>
      channels.value.find(
        (channel) => channel.channelId === selectedChannelId.value,
      ) ?? null,
  )

  watch(
    channels,
    (items) => {
      if (!creating.value && !selectedChannel.value && items[0]) {
        selectedChannelId.value = items[0].channelId
      }
    },
    { immediate: true },
  )

  function selectChannel(channelId: string): void {
    creating.value = false
    selectedChannelId.value = channelId
  }

  function startCreate(): void {
    creating.value = true
    selectedChannelId.value = null
  }

  async function save(input: NotificationChannelSaveInput): Promise<void> {
    try {
      if (creating.value || !selectedChannelId.value) {
        const created = await createMutation.mutateAsync(input)
        selectedChannelId.value = created.channelId
        creating.value = false
      } else {
        await updateMutation.mutateAsync({
          channelId: selectedChannelId.value,
          input,
        })
      }
      message.success('通知配置已保存')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  async function sendTest(): Promise<void> {
    if (!selectedChannelId.value) return
    try {
      await testMutation.mutateAsync(selectedChannelId.value)
      message.success('测试通知已发送')
    } catch (error) {
      message.error(getErrorMessage(error))
    }
  }

  return {
    channelsQuery,
    channels,
    selectedChannel,
    selectedChannelId,
    creating,
    saving: computed(
      () => createMutation.isPending.value || updateMutation.isPending.value,
    ),
    testing: computed(() => testMutation.isPending.value),
    selectChannel,
    startCreate,
    save,
    sendTest,
  }
}
