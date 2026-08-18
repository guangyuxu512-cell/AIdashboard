import dayjs from 'dayjs'
import { computed, ref } from 'vue'

import {
  SHOP_DEVICE_FIXTURE_OPTIONS,
  SHOP_LIST_FIXTURE,
  type ShopListItemViewModel,
} from '@/entities/shop'

import type {
  ShopFilterViewModel,
  ShopFormMode,
  ShopFormViewModel,
} from './types'

function createEmptyFilters(): ShopFilterViewModel {
  return {
    platform: null,
    operationalStatus: null,
    sessionStatus: null,
    ownerName: null,
    keyword: '',
  }
}

function cloneFixtureRows(): ShopListItemViewModel[] {
  return SHOP_LIST_FIXTURE.map((shop) => ({ ...shop }))
}

export function useShopManagementMock() {
  const shops = ref(cloneFixtureRows())
  const filterDraft = ref<ShopFilterViewModel>(createEmptyFilters())
  const appliedFilters = ref<ShopFilterViewModel>(createEmptyFilters())
  const page = ref(1)
  const pageSize = ref(10)
  const detailShop = ref<ShopListItemViewModel | null>(null)
  const detailVisible = ref(false)
  const formVisible = ref(false)
  const formMode = ref<ShopFormMode>('create')
  const formInitialValue = ref<ShopFormViewModel | null>(null)
  const editingShopId = ref<string | null>(null)
  let nextFixtureId = shops.value.length + 1

  const filteredShops = computed(() => {
    const filters = appliedFilters.value
    const keyword = filters.keyword.trim().toLocaleLowerCase()

    return shops.value.filter((shop) => {
      const matchesKeyword =
        keyword.length === 0 ||
        [shop.shopName, shop.ownerName, shop.executionDeviceName ?? ''].some(
          (value) => value.toLocaleLowerCase().includes(keyword),
        )

      return (
        matchesKeyword &&
        (!filters.platform || shop.platform === filters.platform) &&
        (!filters.operationalStatus ||
          shop.operationalStatus === filters.operationalStatus) &&
        (!filters.sessionStatus ||
          shop.sessionStatus === filters.sessionStatus) &&
        (!filters.ownerName || shop.ownerName === filters.ownerName)
      )
    })
  })

  const pagedShops = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return filteredShops.value.slice(start, start + pageSize.value)
  })

  const statistics = computed(() => ({
    total: shops.value.length,
    normal: shops.value.filter((shop) => shop.operationalStatus === 'normal')
      .length,
    sessionWarning: shops.value.filter(
      (shop) => shop.sessionStatus === 'warning',
    ).length,
    automationRunning: shops.value.filter(
      (shop) => shop.automationStatus === 'running',
    ).length,
  }))

  function query(): void {
    appliedFilters.value = { ...filterDraft.value }
    page.value = 1
  }

  function resetFilters(): void {
    filterDraft.value = createEmptyFilters()
    appliedFilters.value = createEmptyFilters()
    page.value = 1
  }

  function openDetail(shop: ShopListItemViewModel): void {
    detailShop.value = shop
    detailVisible.value = true
  }

  function openCreate(): void {
    formMode.value = 'create'
    editingShopId.value = null
    formInitialValue.value = null
    formVisible.value = true
  }

  function openEdit(shop: ShopListItemViewModel): void {
    formMode.value = 'edit'
    editingShopId.value = shop.shopId
    formInitialValue.value = {
      shopName: shop.shopName,
      platform: shop.platform,
      ownerName: shop.ownerName,
      executionDeviceId: shop.executionDeviceId,
      note: shop.note,
    }
    formVisible.value = true
  }

  function saveShop(form: ShopFormViewModel): void {
    const device = SHOP_DEVICE_FIXTURE_OPTIONS.find(
      (option) => option.value === form.executionDeviceId,
    )
    const updatedAtDisplay = dayjs().format('YYYY-MM-DD HH:mm')

    if (formMode.value === 'edit' && editingShopId.value) {
      const index = shops.value.findIndex(
        (shop) => shop.shopId === editingShopId.value,
      )
      const current = shops.value[index]
      if (current) {
        shops.value[index] = {
          ...current,
          shopName: form.shopName,
          platform: form.platform ?? current.platform,
          ownerName: form.ownerName,
          executionDeviceId: form.executionDeviceId,
          executionDeviceName: device?.label ?? null,
          note: form.note,
          updatedAtDisplay,
        }
      }
    } else if (form.platform) {
      const fixtureSequence = String(nextFixtureId).padStart(3, '0')
      nextFixtureId += 1
      shops.value.unshift({
        shopId: `shop-fixture-${fixtureSequence}`,
        shopName: form.shopName,
        platform: form.platform,
        ownerName: form.ownerName,
        operationalStatus: 'normal',
        sessionStatus: 'not_configured',
        executionDeviceId: form.executionDeviceId,
        executionDeviceName: device?.label ?? null,
        automationStatus: 'idle',
        todayGmvDisplay: '¥0.00',
        updatedAtDisplay,
        accountConfigurationStatus: 'not_configured',
        sessionConfigurationStatus: 'not_configured',
        note: form.note,
      })
    }

    formVisible.value = false
  }

  return {
    filterDraft,
    page,
    pageSize,
    detailShop,
    detailVisible,
    formVisible,
    formMode,
    formInitialValue,
    filteredShops,
    pagedShops,
    statistics,
    query,
    resetFilters,
    openDetail,
    openCreate,
    openEdit,
    saveShop,
  }
}
