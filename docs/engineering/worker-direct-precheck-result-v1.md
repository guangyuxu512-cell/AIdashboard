# Worker 预检结果直接回传商品库

商品库通过现有应用接口提交 `douyin.category_schema`，指定 `delivery: product`。中控只选择有权限、在线、已发现店铺且 Worker 版本不低于 `0.5.1` 的设备，保留现有商品版本去重。旧调用不传该字段时继续使用旧协议，便于分阶段升级。

Worker 使用现有本机 RPA Session 和签名链请求平台；完成后先将结果放入现有本机 outbox，再通过 HTTPS 直接 POST 商品库 `/api/v1/worker-precheck-results/{task_id}`。商品库使用现有 Worker 设备凭据向中控只核对该任务和设备的身份，验证当前应用、设备与店铺授权，不向中控发送商品结果。设备凭据只在请求内存中使用，不落入结果、日志或 URL；商品库原有 RPA 只读凭据不具备结果写入权限。

商品库根据任务中的商品和 revision 接收结果，按原规则生成预检结论。相同回执重复提交返回成功，旧 revision 只返回过期回执，不覆盖新预检。商品库提交任务后等待直接结果，不再轮询中控读取结果；等待超时沿用原有幂等提交恢复，不重跑已完成的 Worker 平台请求。

收到商品库回执后，Worker 向中控 `/api/v1/worker/tasks/{task_id}/precheck-delivered` 上报成功或失败和结果摘要，中控不保存类目结果正文。任一网络回执丢失时，outbox 重发同一结果，不重新请求平台。旧中心回传任务和旧 outbox 文件继续兼容。

生产中控地址为 `https://119.29.188.118` 时，Worker 自动使用既有商品库公开地址 `https://119.29.188.118:19001`。其他环境必须显式设置 HTTPS `WORKER_PRODUCT_PRECHECK_ORIGIN`，避免测试结果进入生产；不需要每台生产电脑配置商品库写入 Token。

无 Migration；中控仍为 `20261110_0050`。上线顺序为中控兼容端、商品库接收端、Worker 0.5.1，确认设备授权与真实单项后再启用直接预检。回滚先关闭直接预检入口，保留商品库结果和 Worker outbox；有待发送的直接回传结果时不要直接回退旧 Worker。原有商品库自动预检、RPA 上架及其他任务不属于本次修改范围。

本 Feature 使用新建的隔离库 `control_center_feat_worker_direct_result` 和 `product_workbench_test_direct_v1`，均由现有最小权限应用角色持有；仅对这两个库增加对应的开发连接规则。中控库单一 Head 为 0050，商品库只使用合成测试夹具。没有新 Migration Slot，也没有连接生产库实施开发。

隔离环境通过了中控、Worker、商品库之间的 HTTPS 与 PostgreSQL 联通验证：中控派发一项任务，Worker 直接回传，商品库写入结果，中控仅保存结果摘要。该次 RPA 和平台响应均为合成替身，不作为真实店铺预检通过的证据。
