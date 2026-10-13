# 选品策略 A：已有资源团队处理 Gate 1

2026-10-13，Owner 81a1。沿 `feat/product-selection-strategies-v1`，父候选
`c6298c22378fcfc0b4a88e891875f2ae03b1da98`；精确Green仍
`3128d6ad1048dfda1240148e863ea0c98eb6247f`，origin/main仍
`0102dd6d051f89907bad113c35310bbab69412ec`（本轮fetch核验）。
本文件仅团队修复自检，不宣布条件全接齐、整体Gate2、定时运行或发布完成。

## 缺陷与修复

Feature真实PG先复现：super未选Team编辑已有策略409，选另一有效Team编辑404；
关联Run提交同样被require_team阻止。ca97也独立以集成已有super/策略确认409，
平台/队列前失败，原版本/状态/Run数量未变；此证据为受控API，不是Electron同次点击。

SelectionStrategyService仅对已有资源增加existing_context：先重验人员及模块；
super直接ID查询不套用列表选Team过滤，再从已保存strategy.team_id重新解析有效Actor。
GET/PUT/PATCH和关联手动Run共用它；不改归属、不硬编码Team，不把前端super标记当授权。
普通成员仍SQL Team/Shop授权；新建策略和未关联的草稿Run仍明确业务Team。
类目I/O后再次从原人员和策略重验；撤super并撤店铺授权不会凭旧上下文入队。
保留原CAS、Shop启用/删除校验、签名链路、日期冻结、同key重放及canonical复用。
获取当前草稿不保存名称/状态/条件，也不新建未保存策略。没有新HTTP接口/Schema/配置。

## 实际命令与结果

全部DB测试仅登记的 `control_center_feat_product_selection`，角色 `control_center_dev_user`。
无平台请求；保持单一 `20261013_0044`，0042/0043/0044字节未改。测试夹具按稳定ID清理。

| 命令（相应子目录） | 实际结果/边界 |
| --- | --- |
| backend `.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py -k 'existing_super or resource_team_binding' -q`，修复前 | 3 fail，分别无Team409、另一Team404、关联获取先require_team；未调平台 |
| backend `.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py -q`，修复后 | 17 pass；新增super两种上下文、保存/启停GET回读、草稿关联与回执重放、IO后撤权 |
| backend `.venv\Scripts\python.exe -m pytest` | 630 pass / 231 integration deselected；既有Starlette/httpx弃用warning |
| backend `.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py tests/integration/test_postgresql_selection_realtime.py tests/integration/test_postgresql_selection_runs.py tests/integration/test_postgresql_selection_windows.py -q` | 87 pass，真实PG＋合成平台；旧Run、实时、7d、幂等/迟到及策略权限兼容通过；非平台实测 |
| frontend `pnpm exec vitest run src/features/product-selection` | 13文件 / 93 pass |
| frontend `pnpm lint` | pass |
| frontend `pnpm build` | typecheck及强制Real生产构建pass，18.92s；既有大chunk warning |
| frontend `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts e2e/production/product-selection-strategies.spec.ts --workers=1 --output ../docs/_local/product-selection-strategies-v1/team-crud-real-intercepted` | 2 pass / 40.4s；Real Renderer全部正式API拦截，无真实请求；7d/实时四主题。增加抽屉状态仅草稿、获取不保存、PATCH失败恢复真实状态再成功 |
| root `git diff --check` | pass |

没有新增窗口/启动Electron；截图为Feature浏览器正式API拦截，不能替代原生或真实平台Gate。
原UI字体/主题/排版不改，运行时Frontend文件无变，本轮仅补E2E。没有后端静态工具的新配置或新依赖。

## 交接及后续

提交完整SHA以Handoff回传，不在本文件猜未来commit。ca97应加载匹配后端/Renderer并在同一Electron
检查super未选Team、另一有效Team的列表及抽屉操作；抽屉状态须保存后重新GET，不以可点击算成功。
负向继续用合成普通成员/权限撤回，不停用HuanYu、不破坏有效Session。保存/启停应零Run/平台调用；
关联立即获取只需最小必要链路，已有c629正式实时和77正式7d成功证据保留，不重复认证/盲重试。

A其它industry/date1d/date30d/brand/customprice仍缺直接参数证据，由ca97逐项补证，Owner收到即接入。
B事务/Schema正式提案已提供，尚无新active Slot；先推进时间规则/事务拆取，未验B代码不混入A发布。
回滚保留0044、旧事实及v4兼容Reader，不降级共享库/清数据；Owner不合dev/main、不发布生产。
