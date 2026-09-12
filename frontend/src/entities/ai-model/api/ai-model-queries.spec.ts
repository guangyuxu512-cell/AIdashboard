import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'

import { aiWorkbenchQueryKeys } from '@/entities/ai-workbench'

import {
  aiModelQueryKeys,
  useSetDefaultAiModelMutation,
} from './ai-model-queries'

describe('AI model query invalidation', () => {
  it('invalidates the workbench catalog after an administrator changes a model', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    queryClient.setQueryData(aiModelQueryKeys.list, [])
    queryClient.setQueryData(aiWorkbenchQueryKeys.models, [])

    let mutation: ReturnType<typeof useSetDefaultAiModelMutation> | null = null
    const Harness = defineComponent({
      setup() {
        mutation = useSetDefaultAiModelMutation()
        return () => null
      },
    })
    const wrapper = mount(Harness, {
      global: { plugins: [[VueQueryPlugin, { queryClient }]] },
    })

    await mutation!.mutateAsync('13b4f558-cd56-4f11-99fc-c64275e14031')

    expect(
      queryClient.getQueryState(aiModelQueryKeys.list)?.isInvalidated,
    ).toBe(true)
    expect(
      queryClient.getQueryState(aiWorkbenchQueryKeys.models)?.isInvalidated,
    ).toBe(true)

    wrapper.unmount()
    queryClient.clear()
  })
})
