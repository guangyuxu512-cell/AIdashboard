import { describe, expect, it } from 'vitest'

import { mapShopCreateInput, mapShopDto } from './shop-mapper'

describe('shop backend DTO mapper', () => {
  it('maps only real backend facts into the frontend ViewModel', () => {
    const viewModel = mapShopDto(
      {
        shop_id: '00000000-0000-0000-0000-000000000001',
        display_name: '真实店铺',
        platform: 'douyin',
        enabled: true,
        owner_user_id: '00000000-0000-0000-0000-000000000002',
        note: '真实备注',
        created_at: '2026-08-18T10:00:00+00:00',
        updated_at: '2026-08-18T11:00:00+00:00',
      },
      {
        users: [
          {
            user_id: '00000000-0000-0000-0000-000000000002',
            display_name: '负责人',
            enabled: true,
            created_at: '2026-08-18T10:00:00+00:00',
            updated_at: '2026-08-18T10:00:00+00:00',
          },
        ],
        devices: [
          {
            device_id: '00000000-0000-0000-0000-000000000003',
            display_name: '主设备',
            enabled: true,
            location: null,
            note: null,
            worker_runtime: null,
            created_at: '2026-08-18T10:00:00+00:00',
            updated_at: '2026-08-18T10:00:00+00:00',
          },
        ],
        bindings: [
          {
            shop_id: '00000000-0000-0000-0000-000000000001',
            device_id: '00000000-0000-0000-0000-000000000003',
            binding_role: 'primary',
            enabled: true,
            created_at: '2026-08-18T10:00:00+00:00',
            updated_at: '2026-08-18T10:00:00+00:00',
          },
        ],
      },
    )

    expect(viewModel).toMatchObject({
      shopName: '真实店铺',
      ownerName: '负责人',
      enabledStatus: 'enabled',
      executionDeviceName: '主设备',
      createdAtDisplay: '2026-08-18 18:00',
      updatedAtDisplay: '2026-08-18 19:00',
      dataSource: 'real',
    })
  })

  it('maps create input to the exact ShopCreate contract', () => {
    expect(
      mapShopCreateInput({
        shopName: ' 新店 ',
        platform: 'pdd',
        enabled: true,
        ownerUserId: null,
        note: ' 备注 ',
      }),
    ).toEqual({
      display_name: '新店',
      platform: 'pdd',
      enabled: true,
      owner_user_id: null,
      note: '备注',
    })
  })
})
