# 选品前端验收状态与真实接入资源

2026-10-10，Integrator ca97，Feature Owner 81a1。独立数据库和新 Migration Slot 已分配；请求链路成功证据可复用，真实持久化闭环尚未完成。本轮不发布生产。

## 提交与前端验收

| 项目 | 精确状态 |
| --- | --- |
| Green 基线 | `b34e43cb90356e03d2f793c4146c6775a11f5ab3`；资源登记前 ca97 dev/origin/dev 一致且 clean |
| 当前 Owner | `C:\Users\Administrator\.codex\worktrees\81a1\中控台`，`feat/product-selection-frontend-v1`，HEAD/origin 为 `819ca33ba6548030e418320c6bb80ba046beb842`，clean |
| 前端最终候选 | `06bd03c0fa61b00251063e21350cd0cc5445afe5`；Gate 1 有完整 Handoff，含 lint/typecheck、41 定向单测、13 Mock E2E、Real build |
| Integration 返修复核 | 06bd03c 独立 lint/typecheck/Real build、41 单测、3 定向 Mock E2E、diff check PASS；前一 91461d4 Review2 返修及 Real 无回退证据保留 |
| Electron | 唯一既有开发窗口，5180 的 06bd03c Mock 快照；32 条演示候选。已有交互/主题确认保留，尺寸收尾记录仍为等待最终人工确认，不用浏览器截图补写 Electron PASS |
| dev 合并 | 06bd03c 与 819ca33 均不在基线 dev，未合并，无 Merge Commit；资源登记不代表业务合并或 Green 新功能 |
| 诊断补丁 | 819ca33 是 06bd03c 的直接后续，仅请求层、9 项定向测试及 Backend 说明；两提交 Frontend tree 均为 `0cfd65b3eb7573a2ba5be6b9a7cef08977f85e84`，Electron 树亦相同。定向审查 PASS，不等于完整 Gate 2 |

前端仅确认界面及 Mock 交互，不证明真实采集、持久化、策略保存或调度完成。恢复 Real 后必须没有 Mock 残留/回退，未接入部分如实不可用。

## 已确认取数事实及未知边界

正式认证来自 HuanYu 数据库 ShopSession v1，平台 shop_id `243321624`；链路为 Accessor → 819ca33 DouyinApiClient → 既有 Signer。两次榜单均 HTTP 200、整数 st=0、10 条，basic_info 成功且商品身份匹配。签名 Cookie 与实际 HTTP Cookie 一致，签名后复用同一请求并保持业务 Query 编码。本轮不再追加平台请求。

- 榜单固定路径 `product_rank/video_bring_good`；响应 `data.data_result`、`data.page_result`，商品 ID 为字符串。
- 成功样本为 2026-10-02～10-08、date_type=21、rank_data_type=1、第2页/10条，以及已记录的12个业务字符串参数；这是一次具体条件，不是生产默认、所有渠道/周期的映射依据。
- cate_list 节点 cate_id/cate_name/children、样本行业/类目层级及 basic_info 的 cid_info、first_on_shelf_time 已取得；请求店铺与返回商品商家分离。
- 视频四项 value_range 保留端点、原始 unit 和类型；price 尺度、成交单/件含义未确认。差评率原值 `0.00205018686599039`、unit=4，不换算百分比或用于筛选。
- 商品卡/短视频区分、相对日期与枚举通用含义、类目选择的通用转换、未实测条件仍未知。Real 未确认选项不能静默映射或使用 Mock 补齐。
- 旧 621000704 唯一根因未确定，不阻塞已确认字段和资源准备。

## 两表审查与执行状态缺口

候选身份使用 `(team_id, platform, platform_product_id)` 唯一键；来源观察使用 `(candidate_id, request_shop_id, source_scope_hash)`，不同店铺/期间/条件不互相覆盖。source_context 仅白名单业务参数，来源 hash 版本化且不含页码、认证或追踪值。Team/创建人来自 ActorContext，请求 Shop 指现有授权 Shop，不是商品商家 ID。

平台 I/O 在短事务外；落库前复核权限及停用/移除状态。PostgreSQL upsert/条件回写防重复与迟到旧响应，双 Session 实测是 Gate 1 前置。basic_info 失败保留候选及此前有效值，真实0与缺失分开；列表/详情先做 Team+当前 Shop 授权及来源选择，再排序分页。

两表可保存候选与成功来源事实，但没有候选时无法保存成功空榜单/请求失败的运行状态，也没有已批准的批次关系。现有 Task、经营采集和 AI Job 各有领域约束，不得挪用。新增最小手动 run 表须先审核明确范围；本登记未批准第三表或通用队列/调度。该缺口不影响资源分配，但不能宣称手动执行契约已完整。

降级按来源表→候选表，仅允许在可重建 Feature 库测试，明确删除新选品数据；已有正式数据时应用回退保留 Schema/事实，数据处置另走 Release Gate。无已批准保留期，不增加自动删除。

## 实际资源与初始化交接

| 资源 | 分配结果 |
| --- | --- |
| DB | `control_center_feat_product_selection`，管理员创建空库；Owner `control_center_dev_user`；不复用 Availability/Integration/生产 |
| 应用连接 | 既有 `127.0.0.1:35433` 受信任 SSH 隧道已恢复；StrictHostKeyChecking=yes；实际 SCRAM 连接成功，当前 DB/角色匹配 |
| 最小权限 | CREATEDB=false、CREATEROLE=false、SUPERUSER=false；Feature 库建表/改列/索引权限探针 PASS，事务已回滚，前后 public 表数均0 |
| HBA | 仅新增本 Feature DB + 应用角色 + `172.17.0.1/32` SCRAM 规则，位于 reject 前；解析错误0，reload，无服务重启；其他规则不变 |
| HBA 备份 | 持久化数据卷中的 `pg_hba.conf.before-product-selection-20261010T112247Z`；SHA-256 `4d6671e093bc9fcb1665d207a08ade58806c4a19e7d34b200ea686080ca1eb7a` |
| Head 与 Slot | Integration/生产只读核验均为单一 `20260924_0041`；旧0041 Slot released。新 reserved `20261010_0042_product_selection_manual_v1`，revision `20261010_0042`，down `20260924_0041`；没有新 Migration 文件 |
| 端口 | Owner Backend 8101，Frontend 4176 strictPort；只登记未启动。Integration 保持8100/5180及唯一 Electron，真实平台由 ca97 协调 |
| 凭据 | 复用 Owner 本地忽略配置中的既有应用角色凭据，仅更改目标数据库；不得回传完整连接串，不能继续使用旧 Availability 库 |

81a1 先更新忽略连接，核对实际库名，再执行候选既有 `alembic upgrade head` 并回传单一0041与连接验证。完成后才实施新持久化并验证 Slot 对应 Migration；执行状态缺口和未知请求映射未确认的部分仍不得猜测实现。无需复制生产 Cookie 到开发数据库。

可以继续固定路径解析、错误分层、适配/DTO和离线测试；真实请求→Feature/Integration入库→正式API→Real页面及权限/幂等验证在新的完整 Gate 1/2 候选上完成，再走 Green dev 与适用 Release Gate。
