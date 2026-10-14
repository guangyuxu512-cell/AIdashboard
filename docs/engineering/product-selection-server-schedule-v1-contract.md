# 罗盘服务端选品定时 B 契约（实施及验收记录）

Owner81a1 / Integration ca97 / Main Release。精确A Green
`f5d4866459acf3e29459a9920c03c1e9118a8839`正常no-ff同步为a62a7a7；旧分支与全部验收保留。
0045 Schema技术片段1800f2b，Feature单一20261013_0045、旧迁移字节不改。
**当前仍未完成完整Gate1/100计划及真实自然到期/Electron验收，不是B已部署。**

## 实现边界

- 原StrategyList/Drawer、四主题、A条件/排名/前端成果不重做；原relative条件/Connector/Accessor/Signer共用。
- schedules增加server_selection目标，关联真实策略；不造PC/Skill，不新增表、通用队列或第二扫描循环。
- 手动和定时均进入product_selection_runs及原SelectionRunExecutor；容量等待为pending，不写blocked。
- 策略保存/编辑/启停只同步计划，不请求类目/平台，不创建执行Run。新建明确业务Team；super已有策略按保存归属Team，普通授权不变。
- 百应、达人、手机采集、商品库和自动上架不接；Real未接操作继续不可用，不回退Mock。

## 时间、冻结与重启

每N小时N为正数据库整数、旧JSON默认1：首次启用/时间配置改变为严格下一上海整点，
随后以保存next_run_at为锚连续+N，跨日不重置，不按完成时间累加。名称/条件修改不改变已有锚。
每日沿用上海HH:mm。停用或关闭scheduled清空未来next；重新开启重新生成未来第一时刻。

错过周期仍COALESCE ONE，只记录最近已到期occurrence并推进未来，不补全部历史。
scheduled_for是理论时刻；ScheduleRun.created_at是实际接受/触发时刻，二者不互换。
正式扫描不预置now快照传到事务末；最终接受使用数据库时钟，生成并冻结本次上海相对日期。
相同提交键、回执/轮询/刷新沿旧冻结日期；只保留A的近7天有限补查条件，不扩到其他周期/错误。

## 短事务与幂等

1. 读取due快照，结束读事务；解析保存的人员/Team/module/Shop，事务外读取既有24h类目缓存/必要I/O。
2. 最终事务统一Strategy→Schedule→选品决策锁→canonical，重查配置版本、next/updated、启用与当前授权。
3. 确定性提交键只由Schedule UUID+理论occurrence生成。正式Run/复用回执、ScheduleRun、next一起commit。
4. 相同活动条件安全复用canonical并保留各occurrence回执，不同条件pending排队；容量/忙店不是准备失败。
5. 原执行器短事务领取、事务外平台请求、lease fence短事务写事实。重启回收超时为interrupted，迟到结果不能写。

原unique(schedule_id,scheduled_for)、Team/User/submission_key和活动条件unique保留；提交/复用与claim用同一
选品事务决策锁，完整direct/reused集合两侧相交。同Shop至多1、有效同策略至多1，全局默认3。
只有两个已running的关联冲突，才使用原Run表的受限隔离pending；键为冻结基指纹+稳定S UUID，
不含版本/occurrence/随机值/新日期，先复用已有隔离active，HTTP不能自传。Reader和fence校验snapshot/FK/Shop/hash。
v1–v8无隔离的JSON/hash保持兼容，不重写旧Run；原平台scope/source hash/主备日期/分页不受隔离键影响。

## 权限、状态与查询

服务端不持有人类JWT或假system-super，只用保存的真实User/Team重新解析当前授权；取数前及写入前再查。
停用/删除Shop、模块/Team/人员失权不请求平台；Session失败如实记录并提示登录，不登录循环、不伪成功0。
已接受的旧Run按原规则收尾，停用不创建新的定时执行。

旧PC once/daily/weekly、Task/Worker不变；PC API的列表total、ID、更新、归档及审计都显式target_kind=pc。
原扫描器分目标轮流处理，关闭server开关时不扫描server，不能让server队首阻塞PC。

原策略API追加schedule_available、schedule_execution_enabled、数据库next_run_at及安全latest_trigger。
latest_trigger只暴露ScheduleRun ID/理论与实际时间/受限结果/合法回执与canonical ID/安全code和stage；不返回原message。
无Run的最新blocked不能被旧成功掩盖；新手动提交（含复用、较旧canonical）按提交时间优先于旧blocked。
投影批量查询已授权策略及有效回执，不跨Team/撤权Shop泄露运行记录。

页面在原执行方式位置显示N/真实下次时间，复用原Schedule时区格式化；环境关闭明确显示，不伪造运行。
有定时策略时有限只读轮询，刷新结果只读DB；手动提交可进入原队列，不用页面全局“已有Run”阻止其他店铺。

## 配置与恢复

正式Settings：

| 键 | 默认 | 行为 |
| --- | --- | --- |
| BACKEND_PRODUCT_SELECTION_EXECUTION_ENABLED | false（既有） | 原队列执行与手动提交；关闭后仍可读取已保存结果 |
| BACKEND_PRODUCT_SELECTION_SCHEDULE_ENABLED | false | 新server due生成，必须与execution同时true；Feature/Integration默认关闭真实自动I/O |
| BACKEND_PRODUCT_SELECTION_CONCURRENCY | 3，允许1–20 | 执行worker数量及数据库全局count/claim容量，同店/策略上限仍1 |
| BACKEND_SCHEDULE_SCAN_INTERVAL_SECONDS / BACKEND_SCHEDULE_TRIGGER_BATCH_SIZE | 原10秒/50 | 原PC+server协调器复用总单批上限，不增第二scanner |

生产仅Main在完整Gate/备份/迁移/镜像健康确认后写入既有持久部署配置并启用，不仅改容器临时环境。
先只读核对活动队列及合法计划规模，无测试残留。旧A定时草稿不由迁移INSERT或启动全量转换；
明确范围内通过原正式保存API/Service、当前授权与版本CAS生成未来计划，记录每项转换及next。
未转换旧草稿不能说已自动运行；关闭/失败原因要单独列出。

45 downgrade仅在线精确可重建Feature、锁后无server/hourly/回执引用/多running/隔离元数据；已有PC和A保留。
生产/Integration不降级清历史。新B JSON/类型使用后，应用恢复保留B兼容Reader/PC隔离及Schema，只关闭server生成/必要执行。
旧镜像不能直接读新类型，不将“开关关闭”当任意旧版回退可用。

## 当前实测与缺口

- Schema实际入口纯guard10（与44合跑19有重叠），Feature14组合/FK/唯一/降级及数据保留。
  包含旧PC weekly的local_time/weekday/input/next/人员/时间逐值44↔45不变、旧blocked审计与A策略/观察保留。
- 0045首次42704及回滚44、旧双前缀、未应用45最小修正、成功单一45及八项零计数已登记；ca97恢复active/独立资源接受，不等同Gate。
- Queue三个PG case15.88s：两个running冲突的稳定隔离pending/跨日同键、忙店跳过、6独立进程全局3；合成I/O。
- 新Service五个低并发PG case14.87s：模拟due/原子回执与next/重扫/关闭停用/失败0Run/原执行器入库/Session非空成功/PC正式API及Team隔离。
- 当前Backend默认804 pass/343 integration deselected/64.36s，前端117定向/lint/typecheck及Real build16.22s。
  单轮5项纯测试失败为旧单worker断言/Mock repo缺新validator，按新容量及实际方法补齐后通过，生产代码未为测试绕过验证。
- ca97确认健康恢复、无构建的单次受控窗口后，100计划合成PG **1 pass/231.44s**：100 occurrence/100 pending canonical，重扫0；三消费者最高3、Shop/S不重叠、100 distinct ID且最终100 succeeded，真实平台I/O=0。
  没有100并发连接，准备/触发串行、执行只3worker；先/后八项业务计数均0、单一45、自动两个配置false，全部本次随机UUID夹具清理，没有删旧事实。不重复未变压力组。
- 补六个低并发边界 **6 pass/5 deselected/13.14s**：daily重启只最近一次、prepare中停用/撤Shop授权0Run、两扫描同occurrence唯一、commit前失败全回滚/commit后确认丢失保留且重扫0。
- B最终运行路径旧PC/CRUD/权限/旧Run/完整有效策略集合/N配置/新Schema七文件回归 **91 pass/185.34s**，仅登记Feature+合成I/O；没有重复100压力。
- 旧44迁移保护回归适配45外层后 **3 pass/10.31s**：45→44→43→head事实保留、44拒策略数据丢失、44锁等并发writer后拒绝；只改测试，不改42/43/44/45迁移文件。
- A生产已恢复旧0102/旧Schema43，A新版发布仍由Main处理；不因此回退B Feature45或改A范围。
- 自然到点真实平台→入库→API/Electron、关闭Electron/PC离线、停用后不触发、最终UI尺寸尚需ca97精确候选验收。

## Gate1最终交接核对（2026-10-14）

基线精确f5d4866，远端后续07f1cc7仅AGENTS/工程02/03/A Gate2治理，不替换功能Green。
完整运行代码与上述Schema依赖在同一B分支。最终代码默认Backend **804 pass/350 integration deselected/74.46s**；
Frontend lint、typecheck、14文件**120 tests/14.50s**（117选品+3原Schedule mapper）、Real build**16.28s**，
git diff --check通过。无Electron/Worker/平台HTTP/Signer/Session文件变化，无新安装包需求。
既有Starlette/httpx和Vite chunk warning保留；各轮重复测试不相加伪造覆盖数量。

Feature PG已完成100单次、14Schema/旧PC/A数据保留、3跨进程队列、11due服务（五初轮+六增量）、91七文件回归及旧44保护3项。
所有平台均注入合成adapter、身份/权限与持久化使用真实PostgreSQL；这些不能代替ca97真实HTTP或自然timer。
夹具全为本次随机稳定UUID、stage-2a1前缀，按引用顺序清理；八项前/后均0、单一45、自动两个配置false。
旧正式Session不复制，Feature仍0，不操作Integration/生产、不回写已应用迁移。

ca97接收精确Candidate后独立审查、Integration升级45及原唯一Real Electron，少量合法Session：
在正式页面保存一个未来daily时刻/必要hourly N，等待原scanner自然到点（不能手调executor冒充）；
核对ScheduleRun理论/实际、Run/事实/source/API/UI、关Electron/PC离线仍执行、停用后无新事件、两个窗口与N回读。
真实请求只覆盖必要链路，不重复已确认A品牌/全榜或100请求。Gate2未通过不合dev/main，不部署。

A最终功能Green/main CI和旧生产恢复与B分开：远端main48ca680，实际旧运行0102/Head43健康已由Main/ca97核验，
A新版部署待最小builder选择入口工程授权，当前A/B均不写已部署。B通过后独立Main Release/持久配置启用。
