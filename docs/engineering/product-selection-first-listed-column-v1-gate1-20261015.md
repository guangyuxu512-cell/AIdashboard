# 候选池首次上榜列 Gate 1（2026-10-15）

Owner81a1，沿feat/product-selection-candidate-result-filters-v1，父候选
9734809530f42046293a83c967611f0ac82c07a5。已直接回读规划人类
turn01a13d9c-e651-7aa1-8070-a113549f86a9，要求在列表查看首次上榜，不必逐条进详情。
最终完整Candidate见正式Handoff，保留此前成果，不修改dev/main或生产。

## 最小修改

- 榜单排名后独立84px首次上榜列，NText/现有主题居中显示，true是/false否/null—。
- 数据直接复用详情row.firstListed，正式映射仍dto.newly_on_ranking，后端/模型/Reader均未改。
- 抽取到既有candidate-display的formatFirstListed，详情仅替换原同义表达式，不改详情结构。
- 不从发现情况、首次发现时间、首次上架日期推导；不增加排序、筛选或请求。
- 保留其它字段、260px最小商品信息/固定复制槽、220px操作、64px图片与现有行高。
  列数11→12，按原文本预算扣84px，窄窗口沿既有scroll-x，四字表头可单行。
- 无Backend/Electron/依赖/DB/Migration/策略业务变更，已应用0046不改；无平台/共享库写入。

## 验证边界

格式函数true/false/null与列表NText深度/宽度/无sorter定向测试已补。
浏览器只在独立测试响应中提供三态，不修改原Mock/夹具，验证列表→详情同值；
四主题/普通、宽屏及窄视口沿现有页面检查，商品信息/复制/原排序分页/详情继续回归。
正式API拦截的Real renderer读取已有newly_on_ranking=false应显示否，不回退Mock。
实际命令：frontend lint、build（含typecheck，Real production/18.47s）、受影响代码prettier、
git diff --check通过，只有原有chunk告警。定向unit：19文件143项PASS，包含三态格式函数、
列宽84/不提供sorter、NText深度1/1/3及原选品/共享商品信息/长标签回归。

Mock Playwright按原配置定向5个不同场景：首次整组4/5，详情三态检查误把原上置字段名当
rowheader/同排值查找而失败；只按Naive现有columnheader/下一行实际结构修正测试，
未改详情布局。最终独立复验1/1 PASS/36.3s（截图前归零横纵滚动）；
合计5个不同场景通过，不重复累计。
覆盖四主题1366/1440/1920/2560、附加2240、三态列表→详情一致、商品身份/原字符串复制槽、
行高、排序分页、预览/屏蔽/缺值零值和详情两个时间来源。
Real renderer全API拦截4主题4/4 PASS/59s，正式DTO已有newly_on_ranking=false在列表显示否，
仍无Mock导入；原筛选/批次/URL/基础信息进度保留。浏览器/合成API不是平台或原生Electron验收。

截图与量测在ignored `.codex/selection-first-listed-mock/`（其余4场景）、
`.codex/selection-first-listed-mock-final/`（三态/四主题整页）及
`.codex/selection-first-listed-real-verified/`。运行4176浏览器；不称5180或Electron截图。

## 交接与停止点

提交推送后交ca97仅更新精确Renderer，同一Electron补新列及受影响布局人工确认；
旧策略、长标签及未改内容不重复，但旧确认不自动覆盖新增列。未确认不发布。
真实单商品basic闭环仍由ca97按原Gate2授权边界完成，本UI列不能替代该证据。
用户同时提出的自定义/近7天分页疑问未在本前端小增量擅自改写，单独交原诊断负责人。
