# 运营中心选品与 Worker 契约

- 能力：`douyin.compass_selection`，Python，输入以能力包的 `SelectionInput` 为准；`operation` 为 `categories`、`rank` 或 `basic`，每次选择一台设备上的一家抖店。类目、日期、品牌、价格及商品参数由能力包校验。
- Session 只从该设备 RPA 本地加密资料读取，平台请求在设备上执行；中控和运营中心不接收 Session。正常结果仅包含选品所需字段。
- 中控任务关联 `correlation_id`，相同标识和相同请求只创建一次。Worker 使用自身设备凭据请求 `GET /api/v1/worker/tasks/{task_id}/selection-delivery-context`，然后直接向该上下文指定的运营中心 `POST /internal/worker/v1/selection-results/{task_id}` 回传，成功后请求 `selection-delivered` 确认。
- 回传不可用时结果保存在设备本地 outbox，`selection-delivery-pending` 释放选品执行槽；恢复后重传相同结果，不能重复平台请求。商品库预检继续使用原有队列及并发规则。
- `BACKEND_OPERATIONS_SELECTION_ORIGIN` 是固定的运营中心 HTTPS 基址，不接受任务自带的回传地址。Worker 最低版本为 0.5.9；能力包和 RPA 桥接必须先通过现有签名信任机制。
- 域名路径 `/operations/` 提供独立前端与 API；`/token-admin/_operations/` 只代理 Token 管理和分组范围查询，凭据由调用者提供。
