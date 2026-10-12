# 罗盘策略 A 阶段审查 / Gate 1 技术证据

状态：**PARTIAL**。本候选完成策略管理及已确认条件的实现/自检，不表示A全部条件已接通；
未知参数和ca97真实平台/Electron验收未完成，B尚未实现。交ca97技术审核/补证，不授权越过门禁发布。
阶段候选4e584cb独立技术审查因P1/P2退回Owner；本轮完成下述最小返修后交新精确候选重审，
Slot治理状态仍rejected返修占位，不自行恢复active，不把本次纠错写成完整A Gate通过。

## 基线与范围

- 81a1，`feat/product-selection-strategies-v1`；基线 Green
  `3128d6ad1048dfda1240148e863ea0c98eb6247f`，与已发布
  `0102dd6d051f89907bad113c35310bbab69412ec`业务树一致。
- 保留原策略列表/工具栏/右抽屉、四主题/字体和五项体验；无Electron/PC Scheduler/经营链路改动。
- 真实策略CRUD、服务端分页/名称搜索、version CAS启停；相对条件/全策略计划真实保存。
  保存/启停零run/Schedule、零平台请求。B未接线，计划显示“未调度”，无假next_run_at。
- 原界面“立即获取”关联已保存策略ID/version，独立冻结提交条件；未保存草稿不建策略。
  复用回执有自己的关联/版本，不改canonical；最近结果沿回执取canonical并过滤历史Shop当前权限。
- v3有界1–200官方排名分页、实际total停止、严格newly_on_ranking=true筛选；未知标记不当false。
  启用首次上榜筛选使用独立来源context/hash，不混原口径；原v1/v2解析、fingerprint不漂移。
- 原7日冻结主备、合法空/精确621000704一次补查和Signer链路保留。
  其他周期/品牌/价格/行业仍不可用，未静默替代旧样本或只解除禁用。

接口和复用表见 `product-selection-strategies-v1-contract.md` 及Backend正式Pydantic/OpenAPI。

## 数据库与迁移

ca97登记唯一 `20261013_0044_product_selection_strategies_v1`，阶段退回后状态rejected返修占位；
revision `20261013_0044`、down `20261010_0043`。已分配Feature
`control_center_feat_product_selection` / `control_center_dev_user`、受保护35433，
8101/4176 strictPort。实际Head单一0044、47业务表＋1张Alembic元数据表（public共48表），
末次回读ShopSession/策略/run均0，合成夹具已清理；无生产会话复制。

一张 `product_selection_strategies` 和runs可空策略FK/索引；Team/User/Shop均RESTRICT。
旧0042/0043文件字节、原事实/运行/Session保留。新策略version为正整数CAS，Team仅剩策略亦拒绝删除。
授权先SQL过滤再分页/总数/直接ID；撤权、Shop停用和超级账号无显式Team写均有负向覆盖。

已在该Feature实测：0044→0043→0044保留合成0042事实及0043旧run；新策略存在拒绝降级；
并发未提交writer使排他锁等待、writer提交后降级fail closed，数据保留。
正式环境必须保留新Schema/数据。v3 run及v2首次上榜来源写入后不能直接使用不识别它们的旧Backend；
兼容回滚Backend使用本候选Reader，通过策略管理及执行两个开关停止新写/执行，仍可读策略/新JSON，
见本轮契约；Feature只读保护已实测，真实部署/重启仍须Release核验，不能清表、改JSON或直接降级。

## 实际检查（81a1）

| 位置/命令 | 实际结果与证据边界 |
| --- | --- |
| backend `.venv\Scripts\python.exe -m alembic upgrade head` | PASS，已分配Feature唯一0044，不是Integration/生产升级 |
| backend `.venv\Scripts\python.exe -m pytest` | P1/P2修补后最终代码 **622 PASS**，222 integration deselected；含9项直接Migration目标保护。保留Starlette/httpx既有弃用告警 |
| backend `python -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py tests/integration/test_postgresql_selection_strategy_migration.py tests/integration/test_postgresql_selection_runs.py tests/integration/test_postgresql_selection_windows.py tests/integration/test_postgresql_product_selection.py tests/integration/test_postgresql_selection_categories.py tests/integration/test_postgresql_product_selection_migration.py` | P1/P2修补后8文件 **109 PASS**，真实PostgreSQL/合成平台；CRUD/CAS、配置关闭/换目标、跨策略复用、快照/历史不被编辑覆盖、跨页rank/first flag、权限/撤权、旧链路及迁移Meta/保留/并发拒绝。不是平台真实109次请求 |
| frontend `pnpm lint` / `pnpm build`（内含typecheck，强制Real） | PASS；最终build后扫描无selection-mock-handlers、演示达人值或演示候选；保留原大chunk告警 |
| frontend `pnpm test` | 最终代码 **144文件/649 PASS**。保留原草稿抽屉的回归已修复；既有jsdom XHR stderr未致失败，非零告警声明 |
| frontend `pnpm exec vitest run src/features/product-selection` | 最终代码 **13文件/92 PASS**，新typed API、相对配置/CAS、独立获取、管理只读仍可读、原布局/图片/缓存/失败/时间/Mock边界 |
| frontend `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts e2e/production/product-selection-unavailable.spec.ts e2e/production/product-selection-strategy-restoration.spec.ts --workers=1 ...` | **3 PASS**：Real正式API拦截、原手动回退/刷新/无Mock/权限，以及4主题960/1280/1366/1440/1920类目四列滚动/父级全部/原策略结构；不是Electron |
| 最终 `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts --workers=1 --output ../docs/_local/product-selection-strategies-v1/completion-real-intercepted` | **4 PASS**（上述3项＋新策略流程）：1440×900四主题合成正式API保存/刷新回显、定时草稿、151–200/first、立即获取不保存、启停。最终截图本机忽略；无Backend/平台请求，不是Electron |
| backend原Schedule/请求映射/接口/Source/Connector/DouyinAPI定向 | 74 PASS；后补正整数/旧v2 hash及v3筛选独立契约定向36 PASS，未改Signer算法或PC调度 |
| `git diff --check` / ignored材料核验 | PASS；AGENTS.override、截图/trace/配置未入Git，无凭据内容 |

末次兼容/回滚定向：策略读取在管理开关false仍可用，创建/编辑/启停均拒绝；既有v2活动
default条件被新v3提交复用，canonical不被改写，新回执保留自己的策略版本，重放只有一条pending。
`python -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py`
最终 **14 PASS**。同key跨日先于类目I/O重放原冻结计划，不同key次日不能复用昨日窗口；
默认条件旧v2与新v3仅在完整条件/页范围/冻结日期指纹一致时共享活动任务。

## 阶段退回P1/P2的修补与兼容边界

- P1：旧downgrade未在执行路径核验目标。先用无连接探针复现7类非授权目标均未拒绝，
  再补在线current_database精确登记目标判断；拒离线、Main/Integration/生产、其它Feature及未知目标，
  在LOCK/DDL前执行。探针故意给配置URL的Feature名称，实际查询返回其它名称，不能用URL或包装器assert绕过。
  新 `python -m pytest tests/test_selection_strategy_migration_guard.py` **9 PASS**；
  `python -m pytest -m integration tests/integration/test_postgresql_selection_strategy_migration.py tests/integration/test_postgresql_product_selection_migration.py` **4 PASS**。
  非Feature拒绝测试是无连接合成探针，未连接或尝试降级真实Main/Integration/生产。
  只修尚未过Gate、仅Feature已应用的0044降级保护；upgrade DDL/revision/down_revision不变，
  已有Feature Head/结构/旧事实不需清库或重建，0042/0043文件不改，新Slot不申请。
- P2：先复现关闭旧停用Shop及更换旧停用Shop均409的2项PG/API红测；writable现仅锁当前授权配置与CAS，
  关闭不检查目标ready，开启仍检查；保存校验本次新目标，不因旧目标停用阻止修正。
  停用目标仅允许专用关闭PATCH，完整PUT仍须合法已授权启用抖店。API回归覆盖false、版本冲突、
  开启拒绝、跨Team、撤权、错ID、换有效目标和零Run/零Session/零平台，含在最终109 PASS。
- 返修未修改Frontend/Electron/PC Schedule/请求抽象/Signer；前端649项和4项拦截E2E及截图均来自4e584cb，
  其前端代码与本次修补完全一致，保留证据、不称新增原生Electron验收。不重复不受影响的前端构建。

迭代失败如实保留：初轮旧窗口夹具把总数误设为页长度，77PASS/5FAIL，纠正合成total后完整104PASS；
首次前端精确Body断言未包含新增明确null边界，已更新正式DTO断言；只剩策略保护测试用了错误fixture签名，
修正后11/14及完整104PASS。截图整理曾使用错DOM类名n-data-table-base-body超时，改用仓库已有真实
n-data-table-base-table-body滚动节点后1PASS；不因测试调整改变业务/主题/Mock延迟。
末次全量前端曾645PASS/4FAIL，原因是把“保存未接入”的canSave误用于新建草稿入口；
已修为只有capabilities明确管理只读才禁新增。原抽屉保留测试未弱化，最终649PASS/4项E2E均通过。

## 未覆盖与下一负责人

- A未知：realtime/1d/30d真实枚举和区间、两种品牌枚举、custom price编码/单位/边界、
  其他行业根及对应父级“全部”请求映射。不是Session、DB或Signer未就绪。
- ca97已有合法HuanYu浏览器/会话，原生取证工具无法可靠核验当前URL而暂停；未切换条件/未发新请求。
  只请求用户将现有罗盘短视频Chrome标签置前并回复“罗盘已置前”。不双线索要Cookie/cURL。
- 21名之后/首次标记新候选真实平台对照、策略持久化→Real唯一Integration Electron尚需ca97验收。
  Owner没有发平台请求、写Integration/生产、另开Electron；浏览器API拦截不替代真实证据。
- B仅设计边界，未接服务端hourly/daily、没有新Slot、没有实际到点执行证据，不等待百应/手机。
- 兼容Reader应用回滚、完整A Gate2/Green CI/生产及B真实定时闭环均未完成；禁止写成业务DONE。

Candidate完整SHA、发送结果、最终工作树/DB状态及截图路径在本机Handoff记录；
ca97接阶段审查候选与补证，完成明确范围再走原Gate/独立发布，Main不直接接Feature发布。
