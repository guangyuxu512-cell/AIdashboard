import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppPagination from '@/shared/ui/AppPagination.vue'
import { STANDARD_PAGE_SIZE_OPTIONS } from '@/shared/ui/pagination'

import PaginationBar from './PaginationBar.vue'

describe('PaginationBar', () => {
  it('provides the PC standard page sizes and forwards size changes', () => {
    const wrapper = shallowMount(PaginationBar, {
      props: {
        page: 1,
        pageSize: 20,
        itemCount: 31,
      },
    })
    const pagination = wrapper.findComponent(AppPagination)

    expect(pagination.props('pageSizes')).toEqual([
      ...STANDARD_PAGE_SIZE_OPTIONS,
    ])

    pagination.vm.$emit('update:pageSize', 50)
    expect(wrapper.emitted('update:pageSize')).toEqual([[50]])
  })
})
