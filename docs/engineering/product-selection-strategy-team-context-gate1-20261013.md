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

## 2026-10-13 追加：精确进度读取的团队一致性

沿A当前`8dfb2dcf217b9883e9cd2ddbac9a02da8ee33fc3`继续，B独立
`d4eaa9c4fcf686b2669290aaa45bfc2d577bb2b3`不混入。ca97技术核对认可此尾部缺口；
8df的原生位置专项及既有实时/7d事实保留，不倒写为本次精确进度GET已验收。

已有策略POST已派生资源Team，但`SelectionRunService.get`仍把super的全局Team作为
精确ID过滤；选另一有效Team时提交成功后GET404，未选Team时不复现。
新增Feature PG断言在旧逻辑上1 pass/1 fail，失败为`SelectionRunNotFoundError`。
修复仅在get中重新核验人员/模块及真实super，精确查单个Run，再按已存有效Team复核；
原`_read`回执与canonical的Team/Shop/fingerprint检查保持。canonical可以是旧无strategy
执行，因此不只依赖strategy_id。运行列表继续按全局Team过滤，普通成员SQL/Shop权限不变。
没有提交、事实、保存、CAS、日期、Signer、Session或前端布局变化，不新增API或Schema。

定向覆盖same-header POST202→GET200、同key重放、canonical与reused receipt、旧无关联执行；
普通成员404、资源Team停用拒绝、撤super及Shop授权后缓存super标记无效。
全部仅登记Feature PostgreSQL和合成类目，平台Session入口被测试禁止；无真实请求。
最终追加回归（Backend目录）：

| 命令 | 实际结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -o addopts="" -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py tests/integration/test_postgresql_selection_realtime.py tests/integration/test_postgresql_selection_runs.py tests/integration/test_postgresql_selection_windows.py -q --tb=short` | 92 pass，213.19s；Feature PG＋合成I/O，非平台验收 |
| `.venv\Scripts\python.exe -m pytest --tb=short` | 630 pass / 236 integration deselected，73.38s |
| root `git diff --check` | pass |

保留既有Starlette/httpx弃用warning。精确Candidate随Handoff回传，不在本节猜未来SHA。
测试完成后的额外只读核验因连接对象类型错误失败，异常输出意外包含Feature连接凭据；
未写入Git，本节不复述敏感内容。Owner已停止使用该凭据并通知ca97走受保护轮换/影响核对，
不自行改共享/生产配置。该额外核验不算成功证据，安全事项未核销前不放行完整Gate或发布。

Frontend/Electron/0042/0043/0044与8df字节不变，复用其已记录lint/typecheck/Real build与
95项选品定向和3项完整API拦截证据；不是再次执行，也不是本次新原生验收。
ca97只需加载匹配Backend并补实际现有上下文POST→进度/回执GET，复用不受影响的列表原生专项。
其它行业/1d/30d/品牌/custom price仍待逐项直接证据，B0045仅reserved；A/B整体保持PARTIAL。

## 2026-10-13 ca97追加审查：解析资源Team后的可见性复核

`ed6a98b95b74ca5f2dd29df0e926fdf1db577bd1`的92项PG/630项默认通过事实保留，
但它没有覆盖首次super查行之后、第二次Actor解析之前撤super的交错。
ca97在无配置/无DB的method-only审查中发现：非reused行可能直接被投影，未再次查询Shop授权。
此为真实代码时序的合成证据，不是新PostgreSQL或平台验收。

Owner仅在原get中增加第二次权威Actor下的`get_for_actor`与不可见404；复用SQL/_read，
不新增权限框架或只凭前端/缓存标记判断。正常成员入口保持一次现有查询，super精确ID入口
重新校验Team后查同一个Run；仍有权限的降权成员可按正常授权读取，无授权成员不能复用旧行。
reused回执查canonical也使用该次Actor，Team/Shop/fingerprint边界不变。

新增`test_selection_run_progress_authorization.py`：不构造Settings/Session、不加载配置、不连接
数据库或平台，执行生产get/_read和真实DTO校验，模拟权威Actor/Repository返回的许可交错。
最初夹具漏了正式DTO的brand/price_mode必填值，先修正夹具；此6项初始校验失败不算缺陷复现。
修正夹具后旧ed6为5 fail/1 pass，其中非reused无Shop授权仍返回记录直接复现问题；
其余失败指出缺少第二次精确Run查询或查询了canonical而非先复核回执。

实际命令（Backend）：
`.venv\Scripts\python.exe -m pytest -o addopts="" tests/test_selection_run_progress_authorization.py tests/test_selection_request_mapping.py tests/test_selection_realtime_mapping.py tests/test_selection_strategy_contract.py tests/test_product_selection_source.py -q --tb=short`
结果59 pass，1.42s，包含6项本次进度授权定向。`git diff --check`通过。
Frontend/Electron/Migration仍零变更，未重复其检查；安全hold期间不执行新PG/整体需要DB的验收。
ed6旧PG证据不是本次交错修复已通过PG。共享Role轮换/影响核对及新PG复验仍待处理，
只交无DB代码技术复审，不称Gate1全部完成、Gate2/Green或发布放行。
