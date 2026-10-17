# 商品数据首版开发资源交接

ca97 已接受7d55的最小四表范围并分配唯一 active Migration Slot、独立 Feature 数据库及运行端口。管理员尚需创建空库并交付受保护连接；Owner 在交付前继续离线解析、DTO 和服务验证，不连接其他数据库。

## 授权与基线

直接人类授权来自规划 turn `01a14788-0c80-7b73-be1a-36ad46a23793` 的“那就分配啊”及相邻首版采集入库、查询开发范围。只推进基础手动链路，不授权生产写入、上线、执行清理或新的平台试请求。

Owner：7d55，原工作树 `C:\Users\Administrator\.codex\worktrees\7d55\中控台`，分支 `feat/shop-product-data-real-v1`。从已核 Green `08176d9c5cdbea50114eb0656975a209205761bd` 正常接续并 no-ff 合入原 UI `af6b737281c16e469fdc6300f80cdfb40cb5c981`，当前 `7805ab847976bc5f49e56b49b5e66f362edb49f5`。旧 UI、样本、共享依赖和历史均保留；新的 Green 确认后正常同步，不使用 ca97 未成 Green 的治理 HEAD。

申请为 Owner 本地 `docs/_drafts/shop-product-data-real-v1-schema-request-20261017.md`，审核时 SHA256 为 `C377F15DF51A9106E76042AFDBF2226801F1B8C7F1F51803E19FA0877A7EEE13`。本交接中的约束要求优先于草稿未修订处，不由 Integrator 代写业务代码。

## 已分配资源

| 资源 | 登记与状态 |
| --- | --- |
| Feature DB | 新建独立空库 `control_center_feat_shop_product_data`；已分配，创建及连接交付待 DBAdmin 回执 |
| 应用角色 | 沿既有最小权限角色，由 Admin 核 `NOSUPERUSER/NOCREATEDB/NOCREATEROLE` 等限制；不轮换凭据、不扩大既有权限 |
| 受保护连接 | 仅 Owner 本地 ignored 配置，单独限制文件 ACL；不输出连接串、密码或完整环境行 |
| Backend | Owner `127.0.0.1:8102`，分配时无监听；不得漂移到 Integration/Main/81a1 端口 |
| Frontend | Owner 原 `127.0.0.1:4177 --strictPort`；分配时无监听，不启动第二 Electron |
| Migration Slot | 唯一 active：文件 `20261017_0047_shop_product_data_v1.py`，revision `20261017_0047`，down `20261015_0046` |

35433 复用已登记的严格 SSH 隧道，服务器端同为独立开发 PG 的35433，不是生产 PG。DBAdmin 只建本次新空库；保留旧 Feature、Integration、Main smoke、生产数据及凭据。没有新 Signer、RPA、Worker 或调度服务资源。

## 接受的 Schema 与必须落实的约束

四表分别为 `shop_product_data_products`、`shop_product_data_series`、`shop_product_data_generations`、`shop_product_data_metric_snapshots`。稳定商品键唯一 `(shop_id, platform, platform_product_id)`；字符串平台 ID 不转 Number。序列键包含版本化白名单维度但不含商品、分页或当日起止日期；每代保存冻结的精确日期、时区和切片 hash。

快照复合主键 `(generation_id, shop_product_id)`，17 项原值用精确 NUMERIC，unit/state 为固定17键结构，不存任意原始响应。商品、序列、代和快照用同Shop/同序列复合外键保护，均 RESTRICT；current/previous 不能指向别的序列或相同代。显式 NULL 分支 CHECK、非负计数和单调序号须有 PostgreSQL 回归。

**幂等修正是实施要求：**申请中的 `(requested_team_id, requested_by_user_id, submission_key)` 若 Team 可空，普通 UNIQUE 无法保护无团队超级账号。改用非空 `(requested_by_user_id, submission_key)` 唯一，并在回放前复核请求的 Team、Shop、冻结切片和权限；同键不同请求拒绝。不得通过给超级账号造 Team 解决。相同 active 切片跨团队冲突返回安全忙态，不泄露另一团队的回执 ID、发起人或进度。

提交/领取/finalize 复用现有短事务和持久租约模式。平台 I/O 不在数据库事务内；发布时检查有效 fence、全页完整行集合及单调 sequence，同一短事务更新成功代与 current/previous。失败或迟到代保留已有成功数据，不把未知填0或混用旧代补洞，不加Shop全局锁。

事实读取复用当前正式模块与 Shop 授权；运行回执最窄为当前有效上下文内本人发起且仍有目标权限，超级账号使用既有后端校验。SQL 先限定授权和冻结发布代，再筛选、稳定排序、同集合 total 与分页；默认20，前端翻页/刷新不触发平台。

## 首版范围与实现顺序

首版只实现已有业务样本的基准 `sale_type=1/content_type=1`，近1/7/30对应 `date_type=20/21/23`，请求窗口明确冻结。其他枚举、全部45组合、自定义日期、分组权限、自动每日执行和历史删除均隔离，不静默替换选择，不据文件标签推算未知编码。

复用正式 SessionAccessor、DouyinApiClient 和隔离签名链路，增加端点显式精确数字解码而非第二套 HTTP Client。标题/图片固定路径已有两份历史响应20行观察；原值、合法0、未知、单位未确认分开。金额unit3和比率unit4尚无官方同商品同窗换算证据，原值精度照存，未核定展示/区间筛选保持不可用，不借经营分制或Mock百分比推算。

Owner 现在可完成固定路径解析、合成测试、DTO/Service/Repository及前端窄 Adapter；收到连接后先核目标库，再正式 `alembic upgrade head` 至既有46，随后按 active Slot 实施47、约束/并发/权限/发布回滚的真实 PostgreSQL 测试。正式请求、全页采集及 Integration 真实闭环必须另有指定店铺/窗口/预算授权，开发测试不能冒充平台成功。

当前/上一成功代的读取引用可以实现，历史代和失败摘要暂保留，不执行删除或TTL。新增表升级兼容旧业务；应用回滚保Schema/事实/审计并关新入口。降级只准已登记精确可重建 Feature 库，在线目标核验且四表全部无业务记录；其他库或任一新记录均拒绝，不改0042–0046。

## 下一责任与产物

DBAdmin：确认新库不存在及管理身份后创建空库，核最小角色并交付受限配置，回传目标/Owner/权限/连通白名单事实。7d55：落实幂等修正并更新申请，产出解析测试、Model/Migration/正式API候选与PG记录。ca97：复核资源回执与精确候选，Integration Gate仅写 `control_center_integration`。Main：本次无生产部署任务。
