# 四组无用代码独立清理 Gate 1（2026-10-16）

## 授权、基线与边界

规划核准只读审计后的四组白名单；其余候选均保留。ca97正式交付精确Green
`1773a97d27c56512a620337e3259cceabadca2f1`，Owner再次核实origin/dev及
[CI 38789232361](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38789232361)：
headSha相同，frontend-real-build/backend/container-runtime三Job均success。
在原81a1工作树从该点正常创建`feat/scoped-unused-code-cleanup-v1`，不使用885、旧9bb或后续治理HEAD。
原选品885、纯共享141及所有分支/本机材料完整保留，不混当前Main选品Release。

本任务没有数据库、端口、服务或Migration Slot需求，不解密或输出平台Session/认证载荷，不连接Feature/
Integration/生产数据库，不调用平台/生成API，不操作Electron、Profile、共享stash或他人工作树。
下述既有默认后端测试使用内存Fixture，不是PostgreSQL/Migration证明。

## 实施前只读复核

重新检查Green当前全仓、默认入口、测试、显式/动态注册，并核对实际活跃树：

| 工作树 | 当时精确HEAD | 结果 |
| --- | --- | --- |
| 7d55商品数据 | 03bdc0238465bcad79701af02c04b9811f96a51b | 四组无新调用，工作树干净 |
| 0106 AI | b0c272d1ee13936ae248166baf670a0351bb64c8 | 四组无新调用，旧四mutation仍有消费者，保留 |
| e601 Mobile | 2e95300dbc2c954f302514ca1485ea3e073fc5ac | 四组无新调用，旧四mutation仍有消费者，保留 |

原只读审计另检查main、dev、纯共享141与保留的preflight/release-0037引用。
当前Vite仅vue插件，无Vue组件自动注册；现有import.meta.glob只加载商品照片，不会加载旧Grid。
未在权限模块/CLI发现Legacy类的导入、继承、动态枚举或兼容注册。

## 四组实际删除

| 路径 | 删除范围 | 明确保留 |
| --- | --- | --- |
| `backend/app/modules/access/service.py` | 私有`_LegacyAccessManagementService`整段457行；删除后本文件确实孤立的4个import：AccessAdministratorMembershipUnavailableError、LastAccessAdministratorRequiredError、MembershipModuleAccessRepository、ACCESS_ADMIN_ROLE_CODE | 后方公开AccessManagementService逐字不变；Actor/Module/TeamAuthorization、异常/Repo/角色定义、旧兼容路由/Schema、历史字段和全部迁移保留 |
| `frontend/src/features/ai-workbench/generation/ui/GenerationResultGrid.vue` | 零调用旧组件整文件128行 | 不是InstantResultGrid；InstantResultViewer/InstantResultGrid/BatchResultTree/GenerationRecordDetailDrawer及仍使用的类型、状态元数据、Mock/测试夹具全部保留 |
| `frontend/src/entities/asset/model/useAssetDownloadQueue.ts` | 零调用isAssetDownloadCancelled及仅它使用的ApiError导入 | toApiError、实际取消分类/重试/队列、下载与预览保持 |
| `frontend/src/features/operating-dashboard/model/dashboard.ts` | 零调用formatOperatingDashboardDateRange纯展示助手 | 类型、上海日期计算、真实查询/汇总/覆盖、FilterBar真实日期格式化与采集保持 |

源码差异仅上述4路径，增加本清理记录；没有删除或更改任何测试。
公开AccessManagementService正文对Green做归一换行后的精确字符串比较为true；当前正式Dependency
仍直接实例化公开类，`get_access_administrator = get_super_account`兼容别名不变。

### 明确不删

- Session的Acquire/Release Mutation包装：当前主线零调用，但0106/e601仍由旧ShopConnectionSection调用。
  Validate Mutation和useShopSessionQuery当前主线仍活用；useShopLogin实际datasource链不动。
- Membership Create/Update Mutation包装：0106/e601旧useAccessManagement仍实际调用，保留原导出。
- GenerationSubmitDto公开union alias、GenerationMaterialAssetRole领域预留及其注释均保留。
- API、权限边界、Schema/Migration、依赖、所有Mock/Fixture/测试及已确认候选池/详情/四主题保留。

## 实际验证

| 命令/检查 | 结果 |
| --- | --- |
| Backend `.venv/Scripts/python.exe -m pytest tests/test_access_foundation.py tests/test_access_api.py tests/test_access_management.py` | 22项PASS，3.94s；公开授权、匿名拒绝、Team/模块/资源范围和管理生命周期使用既有默认内存/合成Fixture，不连接真实数据库 |
| Frontend `pnpm exec vitest run src/entities/asset/model/useAssetDownloadQueue.spec.ts src/features/ai-workbench/generation/ui/InstantResultViewer.spec.ts src/features/ai-workbench/generation-records/ui/GenerationRecordDetailDrawer.spec.ts src/features/ai-workbench/generation/ui/BatchResultTree.spec.ts src/features/operating-dashboard/model/dashboard.spec.ts src/features/operating-dashboard/ui/OperatingDashboardFilterBar.spec.ts --maxWorkers=2` | 6文件27项PASS，11.84s；活跃即时/批量/记录结果、取消下载与仅失败重试、日期/汇总/现有筛选 |
| `pnpm lint`、`pnpm typecheck` | PASS |
| `pnpm build` | Real生产构建PASS，Vite15.09s；既有大chunk告警保留 |
| 受保护路径diff检查 | 选品/Shared/app、Session/Access/AI契约、权限Dependency/API/Model/Schema/异常/Repo/角色定义、全部测试、Migration、Electron/Mobile/Worker/lockfile无差异 |
| 删除后引用、旧Grid/活跃Grid路径及公开类正文检查 | PASS：删除符号无调用、旧Grid移除、InstantGrid仍在、公开类逐字保留 |
| `git diff --check` | PASS |

既有InstantResultViewer/BatchResultTree单元测试仍出现jsdom图片XHR AggregateError警告；
测试本身通过。只读核实test模式API base未配置、使用相对`/`；没有为本次清理修改测试/图片组件或
接入真实后端，不将该警告包装成真实下载/平台证据。无生产访问或新平台请求。

未重跑全807/699等未受影响历史套件，不运行PG/Migration、平台或新原生视觉验收；
本次无界面设计变更，不重新要求用户验收已确认选品布局。当前Main选品部署另行进行，
本清理Gate 1与其发布没有包含关系。

## Handoff与恢复

精确新Candidate提交推送后交ca97独立Gate 2；此记录不是Green/集成通过或发布批准。
无新桌面壳/安装包、无数据库操作或自动清理。若出现新引用或删除相关回归，退回本Owner，
只恢复相应白名单项，不在集成树补业务、不顺手重构其它模块。
删除均为Git跟踪源码，可通过保留Green及本清理提交恢复；无需Schema或数据恢复。
清理发布须另行批准，不自动随本次选品部署。
