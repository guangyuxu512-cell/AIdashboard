import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppPagination from '@/shared/ui/AppPagination.vue'
import { STANDARD_PAGE_SIZE_OPTIONS } from '@/shared/ui/pagination'

import PaginationBar from './PaginationBar.vue'

describe('PaginationBar', () => {
  it('provides the PC standard page sizes and forwards size changes', () => {
    const wrapper = mount(PaginationBar, {
      props: {
        page: 1,
        pageSize: 20,
        itemCount: 31,
      },
      // Keep the abstract provider real; a shallow provider stub discards slots.
      global: { stubs: { AppPagination: true } },
    })
    const pagination = wrapper.findComponent(AppPagination)

    expect(pagination.props('pageSizes')).toEqual([
      ...STANDARD_PAGE_SIZE_OPTIONS,
    ])

    pagination.vm.$emit('update:pageSize', 50)
    expect(wrapper.emitted('update:pageSize')).toEqual([[50]])
  })
})
