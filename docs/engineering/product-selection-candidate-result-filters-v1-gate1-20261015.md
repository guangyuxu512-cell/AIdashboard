# 候选池结果、屏蔽与单商品基础补充 Gate 1

Owner81a1 → ca97独立Gate2；本轮未获生产发布授权。精确Candidate以正式Handoff完整SHA为准。
分支feat/product-selection-candidate-result-filters-v1；从精确Green
9bb64ac76bf9e0f51fb1715517cf8c18cef63e22创建，正常no-ff同步资源7dc8034，初始化8f27a8a。
既有A/B发布382ca92/0045、Ops/登录/前端成果不重做、不回滚，不混7d55商品数据前端。

## 改动与复用

- ShopSelector clearable默认false，候选池显式开启；清除→全部授权请求店铺/page1/清勾选/DB读取。
- 原FilterBar/AppSelect增加全部/今日/今日新发现/今日已发现、真实策略名和批次；URL刷新/前后退恢复。
  默认最近真实批次，显式receipt固定；旧未记录不是成功空。策略原最近结果链接该策略真实回执。
- Candidate同Team商品全来源屏蔽/恢复，desired-state幂等及audit_logs原子审计。
- 一张真正canonical rank→Observation不可变成员/最小榜单快照；相对条件发现键与旧日期hash分离。
  今日新后旧两类过滤均保留，先权限/条件后每商品最新匹配来源，去重/稳定排序/分页，不用Run数凑total。
- 单商品“更新基础信息”：现有basic_info及Accessor/HTTP/Signer，不重榜或四视频。复用原Run/Executor、
  全局3/Shop1/租约/fence；只闭式rank/basic_info，不另造队列。basic无策略/计划且saved_count=0。
- 三字段最新尝试与保存值/成功时间分离；失败/null/missing/invalid不清旧值，真实0正常。
  原rank partial及计数不被人工补充改写；已排队/运行/失败/部分成功/更新进度可重新读取。
- 原12列/64px图/约80px行/四主题/策略结构保留；静态未启用大横幅改按钮附近短提示。
  collect/竞品/手机仍未接入，不整体打开service.available、不回退Mock。

正式路由、查询和身份规则见独立contract；schema见Backend04，Front17/05/09与audit说明已同步。
默认及今日结果一商品一行；基础当前事实与历史rank快照时间职责不同，完整来源仍在详情折叠区。

## Migration / 数据保留

唯一active20261015_0046/down20261013_0045，已在control_center_feat_product_selection应用。
SHA256 F87B00229065BADC506CE3BE38E59AB9E7B2DF1833918941D8F4833F924C2F9C。
未改42–45；0046应用后未改DDL。新表RESTRICT/unique(canonical,observation)及必要索引，
Candidate屏蔽/追踪、Run闭式目标/明细版本及条件计数、Observation基础状态/版本均最小增量。
真实Feature metadata一致、46→45→46保留旧候选/策略/B小时计划及PC周计划/运行记录通过。
新语义存在时downgrade拒绝，包含失败/成功空的非NULL明细版本；不清库，不删旧失败/审计。
未批准保留期不自动清理。应用恢复必须保留兼容Reader/Schema/数据及旧运行状态，不能直接退旧Reader。
Integration/生产部署前由ca97/Main按原流程备份和核验Head；Owner不在这两环境迁移或开发。

## 实际验证（不累计重复执行数量）

后端默认：`.venv/Scripts/python.exe -m pytest --tb=short`，807通过/365 integration排除，
仅现有FastAPI httpx弃用警告。受影响纯逻辑追加复验8项通过。

Feature PG：受保护ignored runner核验精确库/role/127.0.0.1:35433，隐藏SQL参数及原异常输出，
运行tests/integration/test_postgresql_selection_candidate_results.py（基础新增16项）、原facts/run、
strategy_compatibility；最终组合63项全部通过。独立Migration组2项通过，B100计划组1项独立通过，
共66个不同PG场景，不把追加复验重复计算。
正式API验证202回执/同key/最近basic进度/blocked列表/跨Team404；数据库保存与读回，非HTTP模拟。
包含两独立Python进程共享领取/忙店跳过、排队后停用0外部调用、失租约旧结果拒绝。

旧B100计划压力组：首轮321.74s报告18通过/1失败，失败为原逐线程55s join结束时消费者尚运行，
不是成功断言通过。现改共同240s有界期限/停止信号并在清理前结束消费者；单独复验1项通过，
仍严格100自然due事件→100唯一Run、100 succeeded、最大3并发/同店及策略不重叠/重扫不重复。
全部平台为合成adapter，非100次真实平台请求；不改生产队列/频率/并发。

前端：lint通过；build（含typecheck、VITE_API_MODE=real）通过，只有既有>500kB分包警告。
选品/Selector/Audit定向17文件124项通过。曾误用pnpm test参数触发全量145文件676项通过，
旧AI jsdom XHR连接错误但断言PASS如实保留；不叠加统计，不声称新AI或付费生成验收。
Playwright Real Renderer/正式API完整拦截：四主题4项通过，1440×900及1366×768，
范围URL/刷新/前后退、精确批次、屏蔽恢复、异步basic禁重复与终态、原视频/时间不变、Real无Mock导入。
真实0、缺值、长标题和固定操作可见；图片加载后截图，已有列表/详情/字体不重新设计。
测试中loading图标改变可访问名称、菜单无option role，按实际控件修测试；未改全局按钮或选择器样式。

## 截图及证据边界

Owner本机ignored `.codex/candidate-result-e2e` 下四组list/detail-{graphite,forest,coral,midnight}.png。
实际运行http://127.0.0.1:4176，Real Renderer/全API合成拦截、非Mock模块、非平台/原生Electron证据。
截图代码与Candidate业务字节对应；ca97须更新精确快照并在唯一Integration Electron补原生Gate。
未启动第二Electron/Backend lifespan、未占8100/5180、未改Profile或复制真实Session。

35433中途断线导致后续测试连接等待：只停止精确归属本轮两脚本的4个Python进程，
ca97正常恢复既有严格隧道；新鲜Feature连接Head46、八项业务数0、执行/调度false。凭据/其它服务不改，
重新连接后继续未完成组，不把隧道恢复当Gate。临时日志/图片/脚本/AGENTS.override均Ignore，不入Git。

## 下一负责人 / 未覆盖

交ca97精确Candidate后独立技术/备份迁移及正式Integration API、唯一Real Electron验收。
Owner只有Feature合成平台+PG+浏览器拦截，没有本候选真实平台响应或生产修复成功证据。
生产目标3848213119470010668历史basic业务拒绝未留HTTP/st/消息，继续UNKNOWN，不伪造响应。
基本补充不能修复其独立视频click invalid。真平台或生产处理须另按既有授权由ca97协调。
旧批次不补造明细；旧逐字段获取时间无证据保持未知。资料采集/竞品/手机/百应不在本轮。
本次无Electron主进程改动或新桌面包，不合dev/main、不发布。Gate2未过不得标完整功能/生产完成。

## Gate 2 返回：长选择标签（2026-10-15）

接续51852，不回退已应用0046或原Gate1成果。AppSelect/ShopSelector新增默认false的labelTooltip，
候选店铺/策略/批次及策略抽屉店铺四处opt-in，复用NTooltip，仅溢出时显示完整文字。
selected布尔同时出现在已选菜单项和选中值，不用它猜渲染上下文；searchable焦点后原生title
消失的路径已实测。默认renderLabel/原生renderTag/close/maxTagCount及必选店铺不变。
不新增选择器/提示Primitive、依赖、全局CSS；不改宽度、业务请求、权限、后端或Migration。

本机Naive2.45.0的NEllipsis初次点击实测抛handleClickRef.value is not a function，未升级或改库；
改复用NTooltip与标签省略样式后点击、搜索、键盘和清除均通过，最终浏览器零pageerror。
初轮测试还因tooltip离场/入场重叠、focused原生DOM及新增批次URL历史定位而失败；按实际结构
和新历史步数修正测试，没有更改业务动画/延迟/路由。原生标签关闭单测将菜单受控为关闭，
只验证close回调，菜单/虚拟列表由浏览器验证，避免将jsdom缺matchMedia当业务失败。

实际命令：frontend lint、typecheck PASS；exec vitest run AppSelect.spec.ts、ShopSelector.spec.ts、
src/features/product-selection、AppButton.spec.ts组合18文件134项PASS；生产Real build PASS/15.21s，
只有既有>500kB分包警告。exec playwright test --config ../.codex/select-label-tooltip-playwright.config.ts：
四主题4项PASS/57.9s，1440×900及1366×768（两尺寸均验证提示边界）、相同前缀A/B完整名称、选项/选中/搜索焦点、
策略/批次、搜索键盘清除、原过滤/URL刷新前后退/屏蔽/basic进度等回归。
全部API拦截，零真实平台，不称Electron/生产验收。

实际截图在ignored `.codex/select-label-tooltip-e2e-final/`，四主题各shop-options、selected-shop、
selected-shop-narrow、selected-batch及list/detail；运行127.0.0.1:4176 Real renderer。Owner未动5180/8100、Profile或原生窗口。
新Candidate完整SHA以正式Handoff为准；ca97更新精确Renderer到同一Electron后补验，仍不标Gate2 PASS或部署。
