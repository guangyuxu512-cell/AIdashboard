# 登录成功提示收尾 Gate 1

本次接续原 98 候选中未发布的成功提示，只补页面级本次保存回执及读取失败提示。Owner 为 81a1，Gate 1 后交 ca97；不重做已经发布的身份、留窗或显式继续流程。

## 精确基线与原候选

- 新分支 `feat/shop-login-success-feedback-v1` 从已核 Green `08176d9c5cdbea50114eb0656975a209205761bd` 正常创建。CI 38982396101 三个 Job 均 success，未使用 ca97 本地纯治理 HEAD。
- 原分支 `feat/shop-login-refresh-recovery-v1` 的完整候选为 `98c1330d8a7f518b18c9f7de40928f31090575ec`，与当前 Green 的共同基线为 1773a97d，尚未包含在 Green 中。
- 对比 a488 到 98 的纯前端差异，当前 Green 仍成功后删除 feedback，且默认 QueryClient 读取失败不 reject。因此成功回执与错误提示确有剩余，不能宣称已被 998/P 覆盖。
- 旧 98 含旧 Backend、Main 和 1.0.7，未整条合并或改写；只逐项复用其前端剩余行为。旧 98、已发布 P d65、1.0.8 包和共享 stash 均保留。
- 已直接回读规划人类 turn `01a14745-c5c5-7263-ba04-a3dc4e576892` 的“下一步”及紧邻范围，ca97 核准原 81a1 工作树纯前端接续，无 DB、端口、Electron、新包或 Migration Slot。

## 本次实现

同店 VALID、新版本、可解析的返回验证时间以及人员/团队/代次检查通过后，清除 active/忙态，但保留页面局部 `success: {sessionVersion, validatedAt, readRefreshFailed}`。只格式化本次返回时间，不用当前时间或旧 Session 元数据补造成功。原短消息和全局 Provider 不变。

保存后的 Shop/Session 两次失效调用局部设置 `throwOnError: true`。读取失败不抹掉权威保存成功，也不归为登录失败；保留真实 Query error、旧缓存和本次保存后的刷新 warning，不重新登录、捕获、确认或取租约。

列表复用原 96px 状态格的 small StatusTag/Tooltip，显示“已更新”或“已保存”，后续服务端非有效状态优先。详情复用原 NAlert success/warning；读取失败时 ErrorState、重新加载及本次保存 warning 共存，不将旧缓存当作 fresh。

已发布 `identityMismatch`、授权目标名、加载/错误分支持续提示及代次/关闭保护保留；错店错误优先于旧成功，不能被成功回执覆盖或重复显示。成功后清掉错店标记，但允许新的本次成功回执保留；取消、关闭等失败收尾仍按原规则。

回执在下次登录、人员/团队/权限变化或离页清除，重进页面不恢复或补播历史成功。再次点击已完成的原窗口只按原权限置前，不重复保存。回执不写 LocalStorage、Query 事实缓存、日志或 Backend。

## 精确修改范围

仅 8 路径，3 个运行文件、3 个测试文件及 2 份契约/交接文档：

- `frontend/src/features/shop-management/model/useShopLogin.ts` 与对应 spec。
- `frontend/src/features/shop-management/ui/ShopListTable.vue` 与对应 spec。
- `frontend/src/features/shop-management/ui/ShopConnectionSection.vue` 与对应 spec。
- `frontend/docs/05-数据模型与接口契约.md`：明确取代 998 当时“不引入成功回执”的范围限定，保留错店保护。
- 本 Gate 1 记录。

两个 Vue 的 style 块逐字不变；列宽、scroll-x、操作顺序、布局、公共组件、主题及全局消息配置保持原样。Backend、Electron/IPC/Preload、实体 API、轮询实现、选品、Worker、包版本、依赖与锁文件无变化。

## 验证结果

| 验证 | 实际结果与范围 |
| --- | --- |
| 只读 QueryClient/QueryObserver 探针 | 默认 invalidate 完成但 Query 已 error，旧 v3 缓存仍在；仅显式 throwOnError 才 reject。全部为合成 queryFn，0 HTTP |
| 新回归在修复前运行 | 筛选子集 8 FAIL / 1 PASS，66 项未选择：三个实际 QueryClient 分支、四主题标签和详情保存回执缺失均复现；无回执 ErrorState 正对照通过。不冒充原 Green 全量测试失败 |
| 四份前端定向文件 | 84 PASS，6.64 秒：model 56、poller 8、详情 11、列表 9。poller 源码和测试未修改 |
| 错店共存与清除 | 错店后成功清错店标记但保成功回执；成功后新错店不被旧回执遮住；加载/error 混入旧 success 仍只显示一个当前错店错误；取消/上下文/离页及重进不重播通过 |
| 实际查询库回归 | 使用真实 QueryClient/QueryObserver、VueQueryPlugin 及原 useShopSessionQuery；Data Source 合成，列表/详情/Session 失败、旧缓存保护、warning 和重新加载均通过，不发平台请求 |
| 四主题 | 使用现有 token/Naive Theme 的实际组件尺寸契约验证 small 标签高度/字号与原值相同、96px/1114px 及操作顺序保持。不是原生截图或新人工视觉确认 |
| Frontend lint、typecheck、Real build | 全部通过，build 19.14 秒；保留既有大 chunk 警告，非平台或 Electron 验收 |
| 格式、diff 与范围 | 仅核准路径；两 Vue style 和排除范围逐字不变。本机 override、临时证据及构建产物保持 ignored |

旧 98 用例按当前 Green 合并适配，不覆盖新增身份回归。原“错店后成功”的断言改为检查错店标记消失且真实本次成功元数据存在，而非要求整个 feedback Map 为空；其余取消/权限/迟到断言不放宽。

## 交接与边界

Owner 本轮无服务/端口、Electron/浏览器窗口、Profile/Session 访问、平台/生产请求或业务数据库操作；不重做旧三轮及生产登录，不注入历史成功事件。数据库、Migration 和安装包均不需要，当前正式 1.0.8/P 保持。

ca97 接收精确新 Candidate 后独立审查并安排新增反馈的适用验收。旧 98 的技术接受、旧浏览器或本次 jsdom 结果都不能代替本候选原生/人工结论。此阶段不合 dev/main，不直接发布；如后续发布，只需配套 Frontend，仍须走 Green/CI/适用 Release Gate。

回退按正式 Frontend 提交恢复，不清 Profile、Session、缓存事实或改数据库。历史 MyCookLab 实际候选来源未知及生产验证预算偏差事实保留，不能从本次提示修复推断历史唯一根因或补写单次 PASS。
