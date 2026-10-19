# 商品数据多店更新与持久队列 V1 — Gate 1 交接

日期：2026-10-19

Owner：81a1

下一责任人：ca97（独立 Gate 2）

## 精确版本与范围

- Green 基线：`915c9d147276aa7bfcd3dabf1385c670c5696c6c`
- Feature 分支：`feat/shop-product-data-batch-queue-v1`
- 实现提交：`bade8bca4d2b959e9029272c1dfe82b75eea590b`
- Migration：`20261019_0048_shop_product_data_batch_queue_v1.py`
- down revision：`20261017_0047`
- 本轮仅覆盖数据中心“商品数据”的多店手动更新、持久队列、并发领取、逐店进度和旧单店兼容。
- 不包含每日自动采集、选品、商品库、手机任务、PC 调度、跨业务店铺锁或通用队列框架。

## 已完成功能

1. 一次提交 1–100 个已授权且启用的店铺；重复店铺及 101 店输入明确拒绝。
2. 新建批次主记录及按店铺 generation 队列项；actor+submission、batch+shop、batch+position、
   同店 running 和状态约束均由 PostgreSQL 保障。
3. 短事务领取、事务外 Session／Signer／HTTP／分页、短事务心跳和原子发布；旧 executor 失去 lease
   后不能更新 Session、进度、终态或事实。
4. 全局并发由配置控制，同一店铺串行；多进程共享数据库领取约束，忙店不阻塞其他可执行店铺。
5. 超时 lease 可恢复；Backend 重启后继续领取持久任务，退出不为不可撤销的同步平台调用额外等待。
6. 平台每页 10 条，默认最多 101 页；完整快照才更新 current pointer，分页／解析失败保留旧成功数据。
7. 保留旧单店提交／查询 API，内部包装为单店批次；新增可采集店铺、多店提交和批次进度 API。
8. 前端支持多店提交、逐店状态、重复点击保护，并按上下文和周期恢复本机记录的活动批次；重开只查询
   数据库进度，不触发新的平台请求。Real 模式不回退 Mock。

## 数据库与配置证据

- Feature PostgreSQL：`control_center_feat_shop_product_data_batch_queue`
- 受限角色／隧道：`control_center_dev_user` / `127.0.0.1:35433`
- `alembic current` 与 `alembic heads` 均为 `20261019_0048`。
- 已验证空库 `0048 → 0047 → 0048`、0047 旧事实往返、模型与 frozen migration、唯一／CHECK 约束、
  两进程领取、lease 恢复、迟到 fence 和 100 店持久排队。
- 验证结束后 batch、generation、snapshot、product、series 表均为 0 行。
- Feature 配置：执行开关 `false`、最大运行数 `1`、最大页数 `101`、lease `600s`、扫描间隔 `1.0s`。
- `alembic check` 因仓库既有、与本功能无关的自动生成漂移退出非零；输出中 Product Data 漂移为 0。
  本轮未借机修改其他模块约束或类型。

## Gate 1 验证结果

### Backend 与 PostgreSQL

- Product Data 非集成定向：152 项通过。
- Product Data PostgreSQL 集成组：68 项通过。
- 100 店同到达持久队列：1 项通过，26.48 秒；使用合成平台，不是 100 次真实请求。
- Product Data Schema 定向：33 项通过。
- Backend 默认离线全量：1085 项通过、459 项 deselected；仅 1 条既有 Starlette/httpx 弃用 warning。
- `python -m compileall -q app tests`：通过。

### Frontend

- 批次操作与 Real API 定向：18 项通过。
- Product Data 全组：15 文件、139 项通过。
- Frontend 全量：170 文件、947 项通过；保留既有 jsdom 图片 XHR 与 Naive 注入 warning，无失败。
- lint：通过。
- typecheck：通过。
- Real production build：通过；仅既有 chunk-size warning。

### 契约与静态检查

- Node 24 / pnpm 11.25 `pnpm verify`：exit 0，0 known / 0 new / 0 stale。
- Node 24 / pnpm 11.25 `pnpm verify --strict`：exit 0，0 known / 0 new / 0 stale。
- Node 24 / pnpm 11.25 `pnpm verify --full --only=backend`：exit 0，1081 项通过、459 项 deselected，
  0 known / 0 new / 0 stale；按契约不运行两个需要端口的用例。
- 系统 Node 20 首次执行 Verify 因 pnpm 11.25 需要 Node >=22.13（缺少 `node:sqlite`）失败；随后使用项目
  工作区运行时 Node 24.19 完成上述三组正式结果。没有修改依赖或降低检查。
- `git diff --check`：通过。

## 权限、并发与失败边界

- 提交前和执行／发布前均复核模块、团队、店铺授权及店铺启用／删除状态。
- 普通用户只能读取本人在相应团队提交且仍具备全部目标店铺权限的批次；超级账号仍校验资源存在。
- 真实 0、未知、失败和未采集不混写；任意分页失败不发布半截快照，不覆盖旧成功 current pointer。
- 本轮没有真实平台调用；Session、Signer 和 HTTP 行为由现有正式适配器加合成响应验证。
- 未启动登记 Backend 8103、Frontend 4178、Electron 或 PC Worker；没有 Integration／生产数据库写入。

## 回滚与恢复

- 紧急停止时先关闭 Product Data 消费者配置；已有 pending/running 记录和成功事实保留，过期 lease 可在恢复
  后由正式领取路径接续。
- 0048 降级仅用于满足精确前置条件的 Feature／受控环境；生产若已有新批次数据，必须先按发布规范备份和
  核验，不以清库或改写已应用 migration 回退。
- 失败 generation 和批次审计保留；不直接改成成功、不删除旧成功快照。

## Gate 2 建议检查

1. 从精确候选独立复验迁移 Head、100 店排队、跨进程全局并发、同店串行和迟到 fence。
2. 在唯一 Integration 实例验证多店提交、关闭／重开后的批次恢复、逐店状态与旧单店兼容。
3. 保持执行开关关闭，除非 Gate 2 明确批准受控平台小样本；不得使用生产做并发压测。
4. 核对 `alembic check` 的非 Product Data 存量漂移边界，不将其误归因于 0048。
5. 通过后再由 ca97 按既有流程推进精确 dev CI；81a1 不合并 dev/main、不部署。

## 未验证／不宣称完成

- 未执行真实平台批量调用、Integration Electron、Hosted CI、dev/main 合并或生产发布。
- 未验证生产容量参数；Feature 环境为最大并发 1 且消费者关闭。
- 本交接证明 Gate 1 代码、数据库与离线契约完成，不代表 Gate 2 或发布完成。
