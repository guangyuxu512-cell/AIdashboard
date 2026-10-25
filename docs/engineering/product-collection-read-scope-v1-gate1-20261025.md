# 采集任务全部团队读取修复

## 基线与交付范围

Owner 为 81a1，下一责任人为 ca97。分支 `hotfix/product-collection-read-scope-v1` 从精确 Green
`1e4feb4c646d2d8031a74d3548ee28273418733b` 创建，已核对
[CI 40173068130](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/40173068130) success。
Candidate 完整 SHA 见正式 Handoff。旧候选与用户未提交的 `AGENTS.md`、`docs/engineering/history/`
及 ignored 本地覆盖文件保持原样，不进入本候选。

本轮只修采集任务列表、总数、详情的读取范围和前端团队切换保护。不改 NAS、手机、采集执行器、
商品库范围、全局权限策略、数据库结构或运行配置，不创建真实采集任务。

## 读取与写入边界

| 当前身份与范围 | 列表和总数 | 直接详情 |
|---|---|---|
| 超级账号，全部团队 | 跨团队，按全局结果分页 | 可读取各团队既有请求及其明细 |
| 超级账号，具体团队 | 只含所选团队 | 其他团队返回 404 |
| 普通成员 | 只含当前有效团队 | 其他团队返回 404；伪造其他 Team Header 返回 403 |

`ProductCollectionHumanRepository.visible_requests` 复用 `DataScopePolicy`，同一 SQL 谓词在
列表分页、total 计算及按 ID 读取前执行。明细和逐状态计数继续绑定已获授权 Request 的真实 team_id。
Service 的两处读取保留 `PRODUCT_LIBRARY` 模块校验，不再调用写入的明确团队要求。

新建、取消、有限重试、重新采集继续调用原 `_write_team`；没有具体 Team 时返回
`TEAM_CONTEXT_REQUIRED`，目标跨团队仍拒绝，不根据全局可见资源推断写入 Team。
普通成员模块撤权后列表与详情仍返回 `MODULE_ACCESS_DENIED`。原认证依赖、团队解析及写校验未改。

前端保留 SelectionWorkspace 的 Actor/Team keyed 面板，补充 CollectionTasksPanel 的同步清空和异步
代次保护。切换时清空列表、勾选、详情和提交幂等回执，重新读取；旧列表、旧详情、旧操作回执不能
恢复先前内容，卸载后的晚到结果不能重启轮询。全局 Real 浏览禁用创建、重试、取消和重采，查询与详情
仍可用。Mock 隔离和现有普通团队交互保持。

## 本轮实际验证

| 检查 | 实际结果 |
|---|---|
| Backend 商品采集隔离单测 | 180 PASS，5.38s；本轮新增 9 项，含 SQL 范围、模块边界及四种全局写入拒绝 |
| Feature PostgreSQL 正式 API | 13 PASS，21.12s；真实 ActorContext resolver、模块 Guard、Header、SQL 分页和详情聚合 |
| Frontend 定向 | 6 文件 31 PASS，7.55s；本轮面板 7 项，另回归 Real adapter、Mock、Auth、HTTP Header 与 Real 不回退 Mock |
| 完整 Backend 离线与 strict Verify | exit 0，114.65s；1261 PASS / 523 deselected，91.72s；known/new/stale 全 0，10 Node / 2 AST / 9 Frontend 契约通过 |
| Frontend lint | `pnpm lint`，exit 0 |
| Frontend 类型与 Real 生产构建 | `pnpm build --outDir ../.codex/product-collection-read-scope-20261025/build-real`，含 `vue-tsc`，exit 0；最终 Vite 构建 17.73s |
| 编译与格式 | 四个 Backend 源码／测试文件 compileall、前端两文件 Prettier、git diff --check 通过 |

定向命令：

```text
# 仓库根目录，使用既有 Node 24 隔离 helper，不加载本机 Backend 配置
node .codex/mobile-media-production-alignment-20261021/run_unit_isolated.mjs
pnpm verify --strict --full --only=backend --report=.codex/product-collection-read-scope-20261025/verify-strict-backend.json

# backend 目录，仅下述已分配 Feature DB
.venv/Scripts/python.exe -m pytest -o addopts= -m integration -q --tb=short -x tests/integration/test_postgresql_collection_read_scope.py --junitxml=../.codex/product-collection-read-scope-20261025/pg.xml

# frontend 目录
pnpm exec vitest run src/features/product-collection src/features/product-library/model/real-boundary.spec.ts src/stores/auth.spec.ts src/shared/api/http-client.spec.ts
pnpm lint
pnpm build --outDir ../.codex/product-collection-read-scope-20261025/build-real
```

修前回归复现全局读取的两处 `TEAM_CONTEXT_REQUIRED`。验证期间修正了测试夹具问题：模块 Repository
未正确替换为 Mock、VNode 空占位索引、PG 唯一超级账号与缺失 synthetic gateway_id。PG 首轮 13 个 setup
error，第二轮 11 PASS / 1 FAIL 后停止，修正测试准备后最终 13 PASS；未为测试修改运行源码、数据库约束或持久化配置。
仅有既有 Starlette/httpx 弃用和 Vite 大 chunk／专属输出目录 warning。运行 Node 24.22.1、现有 pnpm
11.25.0，不改项目 pin 或依赖。

## 数据和环境保护

复用原已分配 `control_center_feat_mobile_product_collection_integration`，角色 `control_center_dev_user`，
隧道 `127.0.0.1:35433`，单一 Head `20261020_0049`。Migration Slot：无；0049 和已应用迁移不变。
三消费者开关均为 false。未启动 Backend lifespan、端口、Electron 或 PC/手机消费者。

测试只在外层事务内构造终态读取样本，各 Service commit 仅释放 savepoint，结束整体 rollback；无可消费
夹具对外可见。已有超级账号只用于读取身份解析，不改其记录。有效创建接口没有生成任务，四种全局写
请求均在写入前拒绝。九张业务表数量与整表摘要前后一致：既有 2 Request / 2 Item / 2 Dispatch / 3 Attempt
保留，其余五表为 0；活动 Dispatch、Pending Item、其他活动数据库客户端为 0。

证据位于 ignored `.codex/product-collection-read-scope-20261025/`：`pg.xml`、`frontend-unit.xml`、
`verify-strict-backend.json` 与专属 Real build；前后摘要为
`.codex/mobile-media-budget-20261021/pg-read-scope-{before,after}.json`。
`frontend/dist` 未改写，既有预览、登录和唯一 Electron 保留。

## 集成和发布交接

ca97 独立 Gate 2 必须加载精确候选的前后端，在唯一 Real Integration Electron 验证：全部团队列表与
total、跨团队详情；切到具体团队后清旧详情并收窄；普通成员直接详情及伪造范围拒绝；全局写入口禁用。
只查询既有任务，不新建或重试采集任务。源码、组件测试或浏览器结果不能替代 Electron 验收。

本 Owner 未执行 Gate 2、GitHub 新候选 CI、dev/main 合并或部署；未对生产/NAS/手机/平台发请求。
Gate 2 和精确 dev CI 通过后交 Main Owner 本地 CD，再核验生产代码、健康及“全部团队”的既有列表与详情。
远端生产 Electron 与本机开发 Electron 分开记录，不能互作证据；没有桌面壳修改，无需新安装包。

回滚采用正常 revert 本候选的读取和前端保护改动，不改任何历史任务、Receipt、商品或迁移。
