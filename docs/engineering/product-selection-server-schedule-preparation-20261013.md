# 选品服务端定时 B：非DDL准备交接

本次只交技术准备，不是B功能Gate1或真实定时闭环。Owner81a1 / 审核ca97。
已按ca97安排创建 `feat/product-selection-server-schedule-v1`：精确Green
`3128d6ad1048dfda1240148e863ea0c98eb6247f`，正常no-ff合入A已交付依赖
`43637bb051d2f4b3ba6c9fab608756429971edd3`，依赖合并
`ecdec1a27a5de0105929209530d79178176ec280`。原A分支不变；未rebase/cherry-pick/reset。
四项B未提交修改以明确路径stash/apply安全移入B，恢复副本保留；没有覆盖其它任务。

## 已实现、未激活的部分

- 复用 schedules/time_rules 增加上海整点next/latest辅助。新接受整点时下一次严格未来；
  旧due整点包含当前时刻，重启选最近一次。跨日/跨年、aware输入、固定上海规则已测。
- PC ScheduleType、Create/Update DTO仍只once/daily/weekly，继续拒绝hourly；
  未改Model、Migration、due scanner、配置或生产；这些函数尚无自动触发调用。
- 现有SelectionRunService只拆出私有 `_persist_submission`，不增第二运行服务/队列。
  原手动外层仍负责权限/Shop/类目/策略CAS、冻结、恢复租约、commit/rollback；
  helper只维护已有savepoint/唯一冲突处理和原回执/活动复用，不HTTP/commit/outer rollback。
  原v2/v3/v4条件/指纹、canonical及策略快照保持，不改变手动请求范围或失败回退。
- PG验证helper返回后的新Run其它连接不可见；同一事务同key一致；调用者rollback后无Run残留。
  通过原有真实PG回归，不把这个内部准备点当成已接到Schedule。
- 原RunRepository增加同策略活动canonical查询，包括该策略复用无关联/另一策略执行的回执。
  双重Team、Shop及指纹约束，pending/running阻止重叠；canonical终态后回执本身不永久锁死。
  只供后续已授权且持策略锁的到期Service使用，本次不改变手动提交或提前开启调度。

## 实际验证

| 命令（backend） | 结果 |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests/test_schedule_time_rules.py tests/test_schedule_service.py tests/test_schedule_scheduler.py -o addopts="" -q` | 26 pass / 1.20s，含9个新增整点/恢复/拒绝边界；PC原once/daily/weekly及scanner保留 |
| `.venv\Scripts\python.exe -m pytest -o addopts="-m 'not integration'" -q` | 639 pass / 232 integration deselected / 69.71s，既有Starlette/httpx warning |
| `.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py tests/integration/test_postgresql_selection_strategy_compatibility.py tests/integration/test_postgresql_selection_realtime.py tests/integration/test_postgresql_selection_runs.py tests/integration/test_postgresql_selection_windows.py -o addopts="" -q` | 88 pass / 229.68s；真实登记Feature PG、全部合成I/O，新增caller事务边界测试 |
| root `git diff --check` | pass |

随后同策略活动查询新增实际Feature PG验证：
`.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py -k 'strategy_activity or shared_run_persistence' -o addopts="" -q`
为3 pass / 17 deselected / 8.80s，覆盖两种canonical归属、pending/running/failed、错Team/ID及caller事务。
这3项与上方88项存在重叠，不相加冒称91项；最新提交的完整五文件回归另记。

包含新增活动查询的最新代码随后执行上述相同五文件完整PG回归：**90 pass / 233.00s**。
前面的88与639/232为首准备提交beaf7ce时的实测快照，均保留，不把重复运行相加。
相对A436，仍无Model/Migration/Schedule DTO/Frontend/Electron变更或平台调用，未激活调度。

ca97已独立接受精确f4非DDL技术准备：隔离归档8文件91 pass，时间/PC service/scanner、
选品mapping/realtime/strategy/source/connector；确认Models/Migration/Scanner/Settings/
Frontend/Electron/Worker无B运行差异。这不是完整B Gate1/Gate2/Release，Owner PG90也不计作Root PG。

后续只新增提交边界的两项PG回归（运行代码相对f4字节不变）：
`.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_strategies.py -k 'commit_failure or shared_run_persistence or strategy_activity' -o addopts="" -q`
为 **5 pass / 17 deselected / 11.40s**。其中3项是既有重叠测试，不和90/91相加：
提交前失败整体rollback无Run；实际commit后确认丢失，跨上海午夜同key重放旧冻结区间、
零额外类目读取且只存一条Run。未commit时没有已接受记录，重试按新的接受日冻结，不伪造旧提交。
均为Feature真实PG＋合成故障，没有平台请求或实际Schedule触发；不代替未来自然定时验收。

DB仍 `control_center_feat_product_selection` / 单一 `20261013_0044`；无新表/列/Slot，
所有已应用迁移字节不变。前端/Electron/Worker无B运行文件改动，不新开窗口、不发平台请求。
当前分支沿用A的前端检查，不重新构建桌面壳，不能据此称B Real/Electron通过。

## 下一步与具体前置

ca97已认可 `product-selection-server-schedule-v1-proposal.md` 的最小结构及短事务方向；
要求FK/partial unique/组合CHECK实际PG验证。0044仍active，按现有串行规则，
A精确Green后ca97释放0044并登记0045(down0044)，之前Owner不得编写/应用B DDL。
不因这项流程停止时间/事务准备，也不抢第二active或通过改0044偷带B结构。
ca97后续明确预留revision `20261013_0045`（reserved，down0044），尚未激活，
仅编号和技术方向批准；不能据此编写/应用Migration。原计划和事实仍是单一0044。

获得正式资源登记后实现target类型/组合约束、策略服务同步唯一Schedule、SQL PC隔离、
原scanner的事务外准备/重锁/原子创建run与触发审计、启停/重复扫描/重启/权限和状态投影。
旧A草稿须正式Service转换未来occurrence，不Migration批量插计划；保留兼容BReader回退。
然后由ca97在唯一Integration进行一次自然到点真实执行、入库/展示以及关Electron/PC离线验证。
当前helper测试和人工执行器都不能替代该证据。未接达人/百应/手机/商品库不扩大范围。

A后续仍由原A分支接每项新的平台映射证据；B后续正常merge A精确Green，不作为A Release目标。
