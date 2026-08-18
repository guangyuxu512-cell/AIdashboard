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

Shop 平台 V1 机器值仅包含 `douyin`、`pdd`；绑定角色机器值为 `primary`、`backup`。
