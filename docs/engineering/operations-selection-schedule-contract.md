# 运营中心选品定时契约

- 运营中心以独立服务身份调用中控 `GET/PUT /api/v1/operations-selection-schedules/{strategy_id}`；`GET .../{strategy_id}/runs` 读取最近 30 次。请求仍需现有定时模块权限和明确团队。
- `PUT` 接受 `name`、`enabled`、`kind`（`daily` 或 `hourly`）、`local_time` 或 `interval_hours`。新计划默认关闭，使用北京时间，不迁移或启用历史计划。
- 现有调度循环到点写入一次待投递记录，并以固定 `submissionKey` 调用运营中心 `POST /api/v1/internal/scheduled-selection`。网络和暂时性服务错误有限次数重投同一标识，运营中心按标识去重。
- 成功记录运营中心任务 ID；失败或停用记录原因。调度前重新校验创建人的权限；被停用的策略不能发起新任务。
- `BACKEND_OPERATIONS_SCHEDULE_EXECUTION_ENABLED` 默认关闭；地址与服务凭据分别由 `BACKEND_OPERATIONS_SCHEDULE_ORIGIN`、`BACKEND_OPERATIONS_SCHEDULE_TOKEN` 受保护配置。旧选品和影刀的开关不因本功能改变。
