# 服务端选品定时 B：最小结构与事务提案

2026-10-13 用户直接要求 A 条件/策略/团队修复继续推进，同时实现 B；Owner 81a1，审核 ca97。
这是待审核提案，不代表 Slot 已激活、Schema 已实现或定时已运行。A 当前已应用 0044，保持字节不变。
B 精确 Candidate 与 A 分离，未验 B 不能混入 A 的发布。新编号及开始写/应用的时点以 ca97 登记为准。

ca97随后技术认可此最小组合/事务提案，要求实际PG证明FK/partial unique/组合CHECK，
不以设计代替测试。已登记B独立 `feat/product-selection-server-schedule-v1`：精确Green3128
正常no-ff merge A依赖43637bb；原A不变。因0044仍active，当前仅非DDL准备，
A精确Green后由ca97串行释放0044、登记0045(down0044)，之前不得编写或应用新DDL。

## 最少结构变化

复用 `schedules`、`schedule_runs`、`product_selection_strategies`、`product_selection_runs`；不新增表。

| 对象 | 拟变更 | 约束/已有数据 |
| --- | --- | --- |
| schedules | `target_kind`：pc / server_selection，旧行 server_default pc | 非空、明确枚举；PC 原行为不改 |
| schedules | 可空 `selection_strategy_id`，RESTRICT FK | 每策略至多一个未归档计划（partial unique）；普通PC必须为空 |
| schedules | `target_device_id` / `skill_id` 改可空 | 只准 server_selection 为空，PC设备/skill仍必须有效；不造假设备/Worker Skill |
| schedules | 内部规则增加 hourly | PC仍仅once/daily/weekly；server仅hourly/daily，Asia/Shanghai、无local_date/weekday；hourly整点，无分钟偏移 |
| schedule_runs | 可空 `selection_run_id`，RESTRICT FK到正式提交回执 | 复用现有唯一(schedule_id, scheduled_for)，无第二执行状态机 |
| schedule_runs | trigger_result 增加 `selection_run` | task_created仅task非空；selection_run仅selection回执非空；blocked两者为空；Service额外检查同Team/目标策略 |

Schedule 组合 CHECK：pc => device、合法 skill 非空且 selection_strategy_id 为空；server_selection =>
真实策略 FK 非空、device/skill/preset 为空、task_input_json={}。server Shop/条件来自当前策略，不复制到PC字段。
保留 execution_display_name（策略名称），不伪装成执行 Skill。旧PC规则/外键/索引/软归档及数据原样保留。
Migration 先核验旧PC/审计组合，若存在不兼容旧行则明确拒绝，不清理或编造关联。
Schedule 与策略的Team/人员一致性及 ScheduleRun 与回执Team/策略一致性由正式Service校验、PG负向验证。

策略 schedule_config 仍是保存/回显输入；B正式Service将其原子同步到唯一Schedule，next_run_at只从Schedule投影。
不独立扫描 JSON、不从前端算下次、不增加另一套调度表。新建/编辑/启停共用现有策略CAS及资源Team规则。

## 原扫描器的短事务与平台I/O边界

不能在持有Schedule锁的事务内调用目前会rollback/commit且读类目的 `SelectionRunService.submit`。
先最小拆出既有准备与无提交的持久化步骤；手动submit仍保留原外层事务、回执、日期、去重契约。

1. 原scanner读取到期Schedule的ID/next_run_at/updated_at、策略version/配置快照，结束只读事务。
2. 用保存的人员/Team重新解析真实Actor与选品模块/Shop授权；在事务外复用24h类目缓存/必要I/O，
   校验真实路径。不冻结日期、不写Run，不用人员JWT/Electron/PC在线状态或伪system-super。
3. 新短事务锁Schedule及Strategy，复核快照、当前enabled/due/target/Team/User/module/Shop及数据库时钟。
   快照失效就放弃，不覆盖新配置。已分类准备失败仍重锁复核，再blocked并推进，不能留热due反复请求。
4. 用既有time_rules选最近已到期occurrence（COALESCE ONE）；scheduled_for只作理论时刻/唯一审计。
   日期在最终接受时用上海实际日期和与手动相同的mapper冻结，不用停机期间的历史理论日期。
5. 正式 `create_for_schedule` 调用共用persist步骤：不HTTP、不自行commit/rollback；
   确定性submission_key由schedule+occurrence生成。同策略活动检查含reused回执的canonical，
   活动未完成时blocked安全原因，不新起重叠取数、不写成功0。手动与due使用同一策略行锁。
6. SelectionRun/回执 + ScheduleRun + next_run_at一次commit；未知异常整体rollback。
   原执行器之后claim、事务外HTTP、短事务事实写入及迟到fence，不另建执行器/队列。

每小时：新建/编辑下一整点严格晚于接受时间；已存在到期整点须执行。每日：用户上海HH:mm。
重启只COALESCE ONE，不补全部错过的周期。停用/关闭定时无新触发，已开始运行正常收尾。
Session失效是明确失败/登录提示，不循环登录或伪空结果。7d窄回退保持原契约；其他周期不套用。

## 开关及 PC API 隔离

服务端定时生产启用要进入现有持久化部署配置，经Release Gate批准。新能力在Feature/Integration默认关闭。
scanner关闭server生成时须在due SQL直接排除server，不因最早server行阻塞PC；原due及审计保留。
原PC列表/total/直接ID/已归档ID/更新/归档/run查询均显式pc过滤，不靠INNER JOIN Device碰巧隐藏。
PC Create/Update/OpenAPI仍不接受hourly/server目标；原TaskService/once/daily/weekly行为不变。
选品Schedule和触发结果只由选品Service/API投影，UI保持已确认结构，真实下次/失败从后台读取。

## 应用、草稿转换及恢复

- 不改已应用0042/0043/0044，不抢第二active Slot。Owner只在已分配Feature DB验证。
- 迁移不INSERT计划/批量补历史。已有A定时草稿须经正式Service、当前授权/CAS、未来occurrence
  按精确记录范围转换，并保留转换结果；未转换不能声称正在调度。
- downgrade仅精确登记的可重建Feature、无server/hourly/selection触发引用时允许；真实运行后保留Schema与历史。
  不降级Integration/生产、不开offline删除脚本，不通过清库规避；测试保留原PC及A记录。
- B存在新类型后不能回退A旧Scheduler/Reader。应用恢复保留兼容BReader和PC隔离，只关闭server生成/执行；
  Main需验证准确回退镜像/持久配置，不能仅关闭开关就称任意旧版本可用。

## 需要完成的证据

Owner：Shanghai hourly/daily及跨年/整点边界；PG唯一occurrence/重复扫描/重启COALESCE ONE；
手动与定时相同条件；保存启停/修改准备期间竞态；reused活动/事务失败；权限、停用Shop、Session失效；PC原API/调度回归。
ca97：精确Real版本自然到点 → 正式Signer/平台 → Run/候选/来源 → API/同一Electron，
另证Electron关闭/PC Worker离线和停用后不触发。合成测试/手调执行器不冒称真实到点验收。
