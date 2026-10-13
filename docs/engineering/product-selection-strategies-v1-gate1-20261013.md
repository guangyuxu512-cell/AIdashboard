# 罗盘策略 A 阶段审查 / Gate 1 技术证据

状态：**PARTIAL**。本候选完成策略管理及已确认条件的实现/自检，不表示A全部条件已接通；
未知参数和ca97真实平台/Electron验收未完成，B尚未实现。交ca97技术审核/补证，不授权越过门禁发布。
阶段候选4e584cb独立技术审查因P1/P2退回Owner；77a1d96最小返修经ca97独立边界接受，
Slot由Integrator恢复active，不是完整A Gate通过。后续继续A现有CRUD验收/逐项接证，不冻结候选或等待B。

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

ca97登记唯一 `20261013_0044_product_selection_strategies_v1`，曾rejected返修占位，77a1d96独立边界接受后active；
revision `20261013_0044`、down `20261010_0043`。已分配Feature
`control_center_feat_product_selection` / `control_center_dev_user`、受保护35433，
8101/4176 strictPort。实际Head单一0044、47业务表＋1张Alembic元数据表（public共48表），
末次回读ShopSession/策略/run均0，合成夹具已清理；无生产会话复制。

一张 `product_selection_strategies` 和runs可空策略FK/索引；Team/User/Shop均RESTRICT。
旧0042/0043文件字节、原事实/运行/Session保留。新策略version为正整数CAS，Team仅剩策略亦拒绝删除。
授权先SQL过滤再分页/总数/直接ID；撤权、Shop停用和超级账号无显式Team写均有负向覆盖。

已在该Feature实测：0044→0043→0044保留合成0042事实及0043旧run；新策略存在拒绝降级；
并发未提交writer使排他锁等待、writer提交后降级fail closed，数据保留。
正式环境必须保留新Schema/数据。v4实时、v3 run及v2首次上榜来源写入后不能直接使用不识别它们的旧Backend；
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

- A未知：1d/30d真实枚举和区间、两种品牌枚举、custom price编码/单位/边界、
  其他行业根及对应父级“全部”请求映射。不是Session、DB或Signer未就绪。
- ca97已有合法HuanYu浏览器/会话，原生取证工具无法可靠核验当前URL而暂停；未切换条件/未发新请求。
  只请求用户将现有罗盘短视频Chrome标签置前并回复“罗盘已置前”。不双线索要Cookie/cURL。
- 21名之后/首次标记新候选真实平台对照、策略持久化→Real唯一Integration Electron尚需ca97验收。
  Owner没有发平台请求、写Integration/生产、另开Electron；浏览器API拦截不替代真实证据。
- B仅设计边界，未接服务端hourly/daily、没有新Slot、没有实际到点执行证据，不等待百应/手机。
- 兼容Reader应用回滚、完整A Gate2/Green CI/生产及B真实定时闭环均未完成；禁止写成业务DONE。

Candidate完整SHA、发送结果、最终工作树/DB状态及截图路径在本机Handoff记录；
ca97接阶段审查候选与补证，完成明确范围再走原Gate/独立发布，Main不直接接Feature发布。

## A管理交互补验（不重做已通过功能）

核对77a1d96源码：CRUD/授权/CAS/编辑回显/独立获取已有实现，无需重写。
原Real拦截E2E虽有PUT处理器和CAS标题，实际未点击编辑保存；本轮补到同一现有场景：
成功PUT→刷新回读、并发版本冲突→保留抽屉/草稿→取消重读、编辑后立即获取当前未保存条件但不保存。
完整过程保存/编辑未创建run，只有显式获取POST /runs；关联保存版本正确，启停真实更新。

- `pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts e2e/production/product-selection-strategies.spec.ts --workers=1 --output ../docs/_local/product-selection-strategies-v1/crud-edit-real-intercepted`（PLAYWRIGHT_FRONTEND_PORT=4176）：**1 PASS**，18.3s测试/22.1s总耗时。
- `pnpm lint`、`pnpm exec vitest run src/features/product-selection` **13文件92 PASS**、`pnpm build`（内含typecheck、Real）PASS。
- 本轮仅补E2E/文档/ca97已确认治理状态，Frontend运行源码/Backend/Migration/Signer/Electron未改，
  不重跑已通过的622 Backend/109 Feature PG或不受影响的原生视觉。保留现有大chunk和NO_COLOR告警。
- 最小API/同一Real页面清单及专用夹具建议已写入契约对应章节，由ca97在Integration自行建立并记录实际结果；
  Owner没有写Integration/真实平台，1 PASS仍是正式API完整拦截，不是Server→DB→Electron证据。

## 第一项参数接证：实时（A仍PARTIAL）

ca97以用户旧明确实时Query和2026-10-13 08:12:39+08 stored HuanYu v6的一次正式只读当前日请求补证：
HTTP200、整数st=0、10条/total200、rank1次/basic0次、无业务写/Run。此为77代码的参数证据，
不是本轮v4入库闭环或同次页面抓包，也不保证平台所有时段可用。Owner未重复请求或改变Cookie/Signer。

v4实时单日冻结、7d旧v3/hash/受限回退保留，实时合法空直接成功0、621/签名等均不走备用。
相对策略配置仍v1；前端原AppRadio和service与capabilities同步开放realtime，来源/详情标签为实时，
备用日期与理由null，缺失值和原始区间保持。0044已由ca97在Integration应用，本次Migration/Schema diff=0。

实际最终检查：

- Backend默认pytest **630 PASS/228 integration deselected**；冻结UTC/上海跨日、旧hash及未知条件门禁等定向 **36 PASS**。
- `python -m pytest -m integration`在前述8文件再加`test_postgresql_selection_realtime.py`：**115 PASS**；
  含实时6项（数据/空态/621 int/string/签名失败无备用、跨日同key重放不读类目、新key新日）及完整旧链路。
- Frontend选品 **13文件93 PASS**，lint/typecheck/Real build PASS；同Real API完整拦截场景按7d/realtime两模式
  测PUT保存/CAS草稿/刷新/独立获取/启停，**2 PASS**（38.9s）；当前截图在ignored `realtime-crud-real-intercepted`。
- 原样保留告警；一次前端夹具把原始0–0误断为0，纠正断言不改范围展示；一次PG旧未知周期测试仍用新已证实时，
  换为仍未确认1d以保留门禁，初轮114PASS/1FAIL后完整115PASS。不是平台或登录故障，未发外部请求。

ca97另已在77正式Integration完成CRUD与零隐式取数，并取得run
`dae3090a-ceb4-44f3-8bba-4bbf362a5cbf`：7d主窗口2026-10-06～12、实际官方rank21–30，
10商品/10来源/API与DB一致；basic_info 9成功1业务拒绝，正确partial且不丢候选，未重试。
category1/rank3/basic10，完成后GET/同key重放增量0，保存版本/条件未改。此未改7d证据可复用，
不把它替代新v4实时完整闭环/first筛选/唯一Electron；剩余参数每项有证据即接，不等待B。

## 通用类目转换接证（A仍PARTIAL）

本轮沿`183b35b4057b979f21a15e117cb2d3e8ef3b9efc`继续，之前“其他行业未知”的限制
由本节新结构证据更新；历史测试/失败/验收记录保留，不要求逐行业建立人工ID白名单。
ca97授权店铺正式GET类目200，现有24小时缓存第二次读取零平台请求，保存完整包装根和下级。
scalar industry_id=7仅为默认选择；ca97从实际树程序读取个护家清/家清纸品，使用当前stored
HuanYu v6及原HTTP/Signer一次只读榜单：industry_id=5、category_id=1000004647、
近7天2026-10-06～12/page1/10，HTTP200/st整数0/10条/total200，未回退/重试/入库。
这些ID是本次证据，不是代码名单；没有同次页面抓包，不能称本新候选完整闭环已验收。

仅2个运行时文件修改：

- `request_mapping.validate_shop_category`：Shop先匹配；包装树按所选实际根匹配行业，
  根下逐层验证真实有序路径，默认scalar不再当行业白名单。旧unwrapped树仍校验原scalar。
- `selection-real-service.categoryNodes`：每个实际包装根派生自己的scope，显示ID保留根，
  请求category_ids排除根。父级全部用原非零前缀；行业根自身仍无scope，0/UI通配符不发平台。

不改变DTO、Schema、Cache key/24小时/命中前后鉴权、类目切店清理、CAS/Team授权、Signer、
日期冻结/有限回退、原布局/主题。保存和编辑回显复用原动态路径解析；未知根全部/其它条件不放开。

实际验证：

| 命令/范围 | 实际结果与边界 |
| --- | --- |
| Backend `pytest -o addopts="" tests/test_selection_request_mapping.py tests/test_selection_realtime_mapping.py -q --tb=short` | 37 pass/1.43s；新增任意合成根41/1082，非默认根与父前缀、错误Shop/行业/逆序/跨根路径拒绝；保留unwrapped |
| Feature PG `pytest -o addopts="" -m integration tests/integration/test_postgresql_selection_strategies.py -k other_actual_industry_parent -q --tb=short` | 1 pass/7.10s；正式POST/保存回读/合成执行/入库，industry41/category4101不被默认7覆盖；非真实平台 |
| Backend默认 `pytest --tb=short` | 638 pass/241 integration deselected/97.52s |
| Feature PG strategies/strategy_compatibility/realtime/runs/windows/categories 6文件，`-o addopts="" -m integration ... -q --tb=short` | 104 pass/249.58s；原权限、进度/回执、幂等/租约、缓存/撤权及新通用路径 |
| Frontend `pnpm exec vitest run src/features/product-selection` | 13文件96 pass/17.66s；非默认root scope、保存/回显/提交、未知root全部仍拒绝、UI原路径/缓存/缺值回归 |
| Frontend `pnpm lint` / `pnpm typecheck` / `pnpm build` | pass；强制Real build25.90s。E2E追加后再次lint/typecheck通过 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts e2e/production/product-selection-strategies.spec.ts --workers=1 --output ../docs/_local/product-selection-strategies-v1/generic-categories-intercepted` | 2 pass/39.8s；真实控件、默认7d与合成非默认行业实时、父级全部/保存重开/提交、四主题；所有正式API拦截，不是Electron/平台 |
| `git diff --check`、忽略材料/无迁移差异 | pass |

保留既有Starlette/httpx、大chunk与NO_COLOR告警；没有用Mock值补真实参数，没有Owner平台请求。
首条服务器只读结构证据、Feature合成DB/Renderer和ca97未来正式入库/原生分别登记。
截图仅Feature浏览器API拦截，四主题同一数据/缩放位于ignored generic-categories-intercepted。

下一ca97加载精确新Backend/Renderer，最小验证一个实际非默认行业父路径选择→保存/刷新→
手动执行→run/事实/API/Real同一页面，复用旧认证成功证据，不逐行业重复请求。
行业根全部尚缺空/省略/0的正常请求证据；1d/30d、两种品牌、20～100元自定义价格继续
由ca97独立查材料/限量单因素服务器对照，Owner确认一项即接；不等待全部条件一起交付。
原生稳定行序尚待用户反馈、整A/B未完成；B0045仍reserved，Owner不合dev/main/发布。
