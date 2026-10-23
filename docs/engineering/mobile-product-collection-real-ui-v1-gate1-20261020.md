# 手机商品资料采集 Real 前端接线 V1 Gate 1

日期：2026-10-20

Owner：81a1

下一责任人：ca97（独立 Gate 2、正式 API 与唯一 Integration Electron 验收）

## 精确基线与候选组成

- Backend 冻结候选：`51cc138af6c265269c2266fe2b43a4a7b6378ea0`。本轮未修改其 API、Schema、
  Migration 0049、消费者或网关实现。
- 已批准前端 Mock／UI 候选：`e52570ffcb8f796301a67ee890ecb2c5f0056925`；本分支通过正常 no-ff 合并形成接线起点
  `aeb9298cf179185c53eddf02c5573a9ee925a0dd`。
- Feature 分支：`feat/mobile-product-collection-real-ui-v1`。最终 Candidate 为包含本记录的 Feature
  HEAD，完整 SHA 以正式 Handoff 为准。
- 本轮仅修改 Frontend 与本 Gate 1 记录；没有 Backend、数据库、Migration、Worker、Electron 主进程、
  依赖、配置或平台请求变化。

## 已完成接线

### 采集任务

- Real 模式使用正式 `/api/v1/product-collection/requests` 列表、详情、创建、取消，以及 Item 级有限
  retry／recapture API；列表摘要和详情分别按正式 DTO 映射，不再回退 Mock。
- 手工提交保持调用方 `submission_key`，请求结果不确定时复用同一个 key；单次最多 100 项的既有边界
  继续生效。活动任务每 2 秒读取正式状态，轮询不会清除当前勾选。
- 页面展示 Request 聚合计数、Item 状态、错误阶段与有限恢复入口。正式列表 API 尚不支持的搜索、平台、
  状态筛选不在 Real 页面伪装成本地全量筛选。
- Real 创建入口只开放 Douyin 商品 ID／受支持链接。PDD 手工完整回传虽属于 Backend 持久化边界，当前
  没有正式派发入口；Taobao 与店铺口令也未接入，均不会在 Real UI 生成任务成功。

### 候选池到采集任务

- 候选 DTO 明确保留 Team 内 canonical `candidate_id`；表格勾选使用 observation row ID，但提交时逐条映射
  到 canonical candidate ID，绝不把 observation ID 当候选主档 ID。
- 单项和批量“采集资料”统一提交 `selection_candidates` 来源；同一 canonical ID 集合复用稳定
  submission key，并区分 submitted、reused 和 failed 回执。成功／复用项取消勾选，失败项继续保留。
- Team 不进入请求 Body，也没有前端默认 Team。共享 HTTP Client 只转发当前显式 Team Context；无 Team
  时不补造 `X-Team-ID`，由 Backend `ActorContext.require_team_id()` fail-closed，超级账号手工输入不会默默
  写入默认 Team。

### 商品库

- Real 模式读取正式分组、商品分页和详情 API；金额仅按正式 cent 字段精确转成两位小数，商品 ID 保持
  字符串。通用 `uu_snapshot`、商家快照和价格证据没有冻结 UI 字段，因此不递归猜字段、不伪造 SKU、属性、
  详情图或精确商品资料。
- 正式 API 当前只支持 search、group_id 与 ungrouped；平台／类目筛选不做当前页假筛选，分组计数未知时
  保持未知，不填 0。
- 商品编辑、分组新增／移动、删除、重新采集、导入和导出都没有正式写 API。本轮在 Real 页面保留既有结构，
  但操作禁用并给出“尚未接入”原因；Mock 交互保持原行为，Real 不显示假成功。

## Gate 1 验证

| 检查 | 结果 |
| --- | --- |
| Real 接线定向 Vitest | PASS：8 文件／54 项；覆盖正式 Request 映射、稳定提交、PDD／Taobao／店铺口令 fail-closed、商品库只读边界、canonical candidate ID 和既有 UI 回归 |
| Frontend 全量 Vitest | PASS：175 文件／969 项 |
| `pnpm run lint` | PASS |
| `pnpm run typecheck` | PASS |
| `pnpm run build`（`VITE_API_MODE=real`） | PASS：5834 modules；仅仓库既有 chunk-size warning |
| Prettier（全部本轮 TS／Vue 路径） | PASS |
| `git diff --check` | 最终提交前复核；应为 PASS |

全量测试保留仓库既有 jsdom 外部图片 XHR `AggregateError` 与 DataTable 缺少测试 Provider 的 warning；
175 个测试文件全部通过，没有新增失败或跳过。

## 未执行与 Gate 2 清单

- 本工作树没有连接 Feature／Integration／生产数据库，没有启动 Backend、Frontend、Electron、网关或手机，
  没有写 5180/Profile，也没有真实平台或设备请求。因此本 Gate 不能标成“真实手机闭环已验收”。
- ca97 应在精确 Candidate 上验证：模块权限、明确 Team 与超级账号无 Team 的 fail-closed、手工 Douyin 创建、
  候选 canonical ID 创建、重复 submission 复用、状态轮询、有限 retry／recapture、商品库刷新后可读，以及
  Real 无 Mock 回退。
- PDD 只保留 Backend 已冻结的 manual-return 数据边界，不在本轮显示为可自动采集；Taobao 未接入。
  商品库正式写操作、导入导出和重新采集仍为后续接口范围。
- 真实设备配对与一台设备闭环继续由 ca97／外部 Owner 在隔离环境完成；本前端 Gate 不占用该流程。
- 私有仓库边界：本轮只本地 commit 与精确 SHA Handoff，不 push、不创建 PR、不触发 Hosted CI，不合
  dev/main、不发布。回退只需正常 revert 本前端 Candidate；Backend 与 0049 无需回退。
