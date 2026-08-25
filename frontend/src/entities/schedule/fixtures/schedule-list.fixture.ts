import type {
  ScheduleListItemReadDto,
  ScheduleReadDto,
  ScheduleRunReadDto,
} from '../api/contracts'

const latestRun: ScheduleRunReadDto = {
  run_id: '70000000-0000-4000-8000-000000000001',
  schedule_id: '60000000-0000-4000-8000-000000000001',
  scheduled_for: '2026-08-24T01:30:00Z',
  task_id: '10000000-0000-4000-8000-000000000004',
  task_status: 'success',
  trigger_result: 'task_created',
  trigger_error_code: null,
  trigger_error_message: null,
  created_at: '2026-08-24T01:30:00Z',
}

export const SCHEDULE_LIST_FIXTURE: ScheduleListItemReadDto[] = [
  {
    schedule_id: latestRun.schedule_id,
    name: '每日商品发布（Fixture）',
    enabled: true,
    target_device_id: 'device-fixture-003',
    shop_id: 'shop-fixture-003',
    device_display_name: '深圳-工作站-03',
    execution_type: 'yingdao_application',
    skill_id: 'yingdao.app.run',
    execution_display_name: '商品发布（Fixture）',
    schedule_type: 'daily',
    local_time: '09:30:00',
    timezone: 'Asia/Shanghai',
    next_run_at: '2026-08-25T01:30:00Z',
    latest_run: latestRun,
    created_at: '2026-08-20T03:00:00Z',
    updated_at: '2026-08-24T01:30:00Z',
  },
  {
    schedule_id: '60000000-0000-4000-8000-000000000002',
    name: '库存同步（Fixture）',
    enabled: false,
    target_device_id: 'device-fixture-002',
    shop_id: 'shop-fixture-002',
    device_display_name: '上海-直播机-02',
    execution_type: 'yingdao_application',
    skill_id: 'yingdao.app.run',
    execution_display_name: '库存同步（Fixture）',
    schedule_type: 'daily',
    local_time: '22:00:00',
    timezone: 'Asia/Shanghai',
    next_run_at: null,
    latest_run: null,
    created_at: '2026-08-21T03:00:00Z',
    updated_at: '2026-08-23T03:00:00Z',
  },
]

export function scheduleFixtureToDetail(
  item: ScheduleListItemReadDto,
): ScheduleReadDto {
  return {
    ...item,
    application_id:
      item.schedule_id === latestRun.schedule_id
        ? 'app-fixture-product-publish-1'
        : 'app-fixture-inventory-sync-2',
    parameters: {},
  }
}
