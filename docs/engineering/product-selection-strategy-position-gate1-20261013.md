# 选品策略 A：启停/编辑列表稳定性返修

Owner81a1已回读ca97人类原始turn `01a13455-37ce-73f0-a5c5-f81e54ceb14e`。
在A `feat/product-selection-strategies-v1`、父候选43637bb继续；B d4eaa9c及原分支/材料保留，未混入。
本项不依赖新的罗盘参数，不等其它条件一起确认；整体A仍PARTIAL，精确候选交ca97补原生专项。

## 实际原因和改动

1. 后端列表按updated_at DESC，启停/保存真实更新时间后重新查询导致变位。
   改为不可变created_at DESC + strategy_id ASC；同创建时间有稳定键。
   不停写/伪造updated_at，不改变授权/搜索先于排序分页的边界，不新增排序页面或Schema。
2. 原StrategyList.saved()对已有编辑也无条件setPage(1)。现在已有编辑保持页和筛选；
   仅新建回第一页，nextTick后读取对应查询。改名不再命中筛选时服从正式过滤。
3. Drawer把正式保存返回值传给列表；启停也使用正式返回值。按稳定ID原位替换当前Query记录，
   不unshift/重排，不建立第二个row store；不以较旧版本覆盖新缓存。随后正式GET更新最近结果。
   未挂载/上下文已变的启停迟到响应不写缓存；失败保留真实状态及编辑草稿。
4. 保持原DataTable/AppTable、rowKey、布局、主题和控件，不加scroll补丁/全站样式。
   API响应刷新不替换表格组件，普通页面和固定列仍由既有组件处理。

## 证据与实际验证

- Feature真PostgreSQL先复现2个排序失败，修复后2 pass / 17 deselected / 10.94s。
  创建时间不同/相同、跨三页，启停/编辑/version/真实updated_at、最近Run与普通成员隔离。
- `backend .venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py -o addopts="" -q`：21 pass / 56.24s，
  当前登记Feature单一0044、合成I/O；含原资源Team/CAS/保留成功与兼容，不调用平台。
- `frontend pnpm exec vitest run src/features/product-selection`：13文件95 pass / 15.62s。
  新增已有保存留page2/原搜索、新建回page1、启停正式响应原位更新（GET尚pending时含version/最近结果）。
- lint、typecheck及强制Real production build通过；最终源码补迟到保护后再验lint/build
  （17.84s，既有大chunk warning）及List/Drawer14 pass / 8.97s。未将重复执行计数相加。
- Real Renderer全部正式API拦截E2E：7d/实时原策略CRUD/CAS/草稿不被获取保存、开关失败恢复，
  四主题检查；新增60策略夹具第二页/搜索/启停/编辑/横纵滚动保留。合计3 pass / 41.3s，
  前端4176 strictPort，不启动Backend/Electron或请求平台。**不能当真实平台或原生Electron证据。**

命令：`PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts e2e/production/product-selection-strategies.spec.ts e2e/production/product-selection-strategy-position.spec.ts --workers=1 --output ../docs/_local/product-selection-strategies-v1/stable-position-real-intercepted`。
使用既有已安装headless runtime。首次No tests found因新文件未登记，已补正式白名单；
一次单测stub未命名造成空Wrapper，已修正测试夹具。滚动初测在控件被固定列遮住时点击：
保持PATCH响应挂起验证，滚动发生于输入定位、不是接口刷新。修正为先滚动完整露出控件再测，
点击前/响应前/GET及保存后位置一致，不靠页面CSS或强制点击掩盖失败。
不把这些最初未执行/失败当通过，也不将重复测试计数相加。

## 门禁与后续

无新API/平台映射/Schema/Migration/配置；0042/0043/0044不改，0045预留不激活。
不重复Backend不受影响全量、真实平台请求或桌面构建；Electron壳字节不变，无需新安装包。
ca97收到新精确Candidate后更新匹配Renderer/Backend，同一5180→8100→Integration及唯一Electron。
由于List/Drawer确有运行字节变化，加载前按正常交互处理当前未保存草稿，不能用HMR静默丢掉；
保留Profile/登录，不新开验收窗口。核验第二页/筛选下启停与编辑、GET版本及真实更新时间、
滚动和失败草稿，浏览器拦截不能替代该原生专项。
其它industry、1d/30d、brand/customprice由ca97单因素补证，Owner每确认一项即接入；本项先交付。
完整A Gate/精确CI Green后Main发布及ca97串行激活B；本项自检不等于整体A发布完成。
