# 数据库与 Migration 规范

数据库渐进式演进，不要求一次设计所有表。

新需求先判断：
- 新属性
- 新实体
- 新关系

## 主键
使用稳定 ID，禁止名称主键。

## 多对多
明确可能多对多时使用关系表。
例如 `shop_device_binding`。

## Migration
所有结构变化通过 Alembic。
禁止直接手改正式 DB。

## 索引
根据实际查询条件补索引，不无依据创建大量索引。

## 敏感数据
Credential / Session 与普通业务字段分离并加密。

## Core Domain V1 数据库

首个正式业务 Migration：`20260818_0001_core_domain_v1`。

| 表 | 职责 |
|---|---|
| `users` | 最小系统用户身份，供负责人等稳定关系引用 |
| `shops` | 店铺基础事实、平台、启用状态、可选负责人和备注 |
| `devices` | 设备身份、启用状态、可选位置和备注 |
| `shop_device_bindings` | Shop 与 Device 的 PRIMARY/BACKUP 关系及启用状态 |

核心 ID 使用统一 UUID；核心表使用带时区的 `created_at`、`updated_at`。`shop_device_bindings` 使用 `(shop_id, device_id)` 复合主键防止重复关系，并使用 PostgreSQL 部分唯一索引保证每个 Shop 最多一个启用 PRIMARY。

Migration `20260822_0008_shop_soft_delete` 为 `shops` 增加可空 `deleted_at` 与查询索引。`enabled=false` 只表示业务停用，`deleted_at IS NOT NULL` 才表示从正常业务视图移除；软移除不级联删除 Credential、ShopCredentialBinding、ShopSession、Task 或历史数据，`shop_id` 永不复用。

Shop 平台 V1 机器值仅包含 `douyin`、`pdd`；绑定角色机器值为 `primary`、`backup`。

## Authentication Domain V1 数据库

Migration `20260819_0002_auth_domain_foundation` 增加：

| 表 | 职责 |
|---|---|
| `platform_credentials` | 平台、统一登录标识、加密 Secret、验证码渠道与启用状态 |
| `shop_credential_bindings` | Credential 与 Shop 的可扩展关系；每 Shop 最多一个启用关系 |
| `shop_sessions` | 每 Shop 当前 Session 元数据、乐观并发版本与加密 payload |

外键统一 `RESTRICT`，避免无意级联删除认证事实。Session 版本必须为正整数，更新由 Service 使用条件更新原子递增。真实迁移闭环只允许在可随时重建的 `control_center_dev` 执行。

## Device Provider Inventory

Migration `20260820_0005_provider_inventory` 增加
`device_provider_inventory`。它以 `(device_id, provider_code)` 为复合主键，只保存
每台设备、每个 Provider 最近一次上报快照。Provider 的未安装、版本不支持、需登录、
接口不可达和 ready 都是正常 Inventory 状态；上报这些状态不删除 Device Runtime。
`inventory_payload` 是外部 Provider Inventory 的专用 JSONB，并用对象类型约束，
不得演变为任意业务数据容器。当前影刀应用数组保留在该快照中，等真实 Skill 与 App
绑定或版本管理需求出现后再独立建模。

Migration `20260823_0011_automation_application_configs` 增加
`automation_application_configs`，以 `(provider_code, app_id)` 唯一保存通用自动化应用的
参数 Schema、默认值、来源和版本。V1 的 `schema_source=manual`，只支持 text/number/
boolean/select；不得把 Credential、Cookie、流程内容或任意 Provider 原始响应放入该表。

## 阶段 3D-1 持久结构

- `devices.deleted_at`：Device 软移除时间，UUID 和历史引用不删除。
- `device_runtime.connection_status/offline_since`：持久化转换前状态，避免 Backend 重启制造重复离线通知。
- `notification_channels`：全局通知通道；Webhook URL 仅以 SecretCipher 密文保存。

Migration 对既有 Runtime 按当前 45 秒阈值回填状态，但回填过程不产生通知。

## Task Runtime Event

Migration `20260822_0010_task_runtime_events` 增加 `task_events`。它只保存 Task 运行事件
流水，不是通用日志平台。`(task_id, seq)` 唯一并建立同序查询索引；metadata 使用受限
JSONB 对象，不得保存 Cookie、Token、Credential 或完整敏感任务输入。
