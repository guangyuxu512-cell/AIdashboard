# 经营采集会话恢复集成验证

Candidate `3f88e4f2fb60aa6d5da829ad5afb6948a71d557a`，Feature Owner 81a1，唯一直接父为精确Green `bef7093b755cea60fda55bbcc6177b5723d4738a`。ca97已完成独立源审、Integration PostgreSQL、精确构建及实际5180的页面自动化；工具拒绝的前端切换已由用户正常本机执行，实际5180/8100均核对为匹配候选。接受本候选Gate2，随后按流程正常no-ff、复验及精确dev CI；此时尚不是Green，不发布或执行生产补采。

## 范围和独立审查

远端Feature与本地Candidate一致，共23个路径，改动为经营恢复资格投影、原单项retry显式复核、原执行器专有只读事务边界及Renderer接入、测试和契约。Migration和Electron相对Green完全未变，无新Slot或安装包；不加入商品数据、选品、视觉Token或verify工程。

已核DAILY/FAILED/retryable及安全失败码白名单、原Item去重、默认300/301秒门槛、显式布尔与精确版本、原累计次数/历史保留、授权/停用/09:00边界。权威会话复核仍由原collector的HealthService执行，HTTP提交只排队；默认Health调用方和候选登录保存不绑定事务回调。新恢复操作通过既有Job轮询和正式读库完成反馈，含pending首个GET等待期及人员/团队/卸载迟到保护。

生产只读证据的固定8项为HuanYu 2026-10-10/11、MyCookLab 2026-10-10至15；资格阻塞已确认，但历史平台失败的唯一原因未确定。本轮没有对这些生产日期发起请求或写入，不能把合成样本的恢复结果外推为生产已补齐。

## ca97实际验证

| 验证 | 结果及边界 |
| --- | --- |
| 独立精确归档后端定向回归 | 10文件129通过，0失败或错误 |
| 独立经营前端测试 | 7文件38通过，0失败或待执行 |
| 静态和Real production构建 | lint/type通过，构建19.53秒；保留既有大chunk警告 |
| Integration PostgreSQL | 8通过，56.02秒；精确control_center_integration、最小角色、单一20261015_0046 |
| 数据保护 | 每例前后19张旧表计数及全字段服务端摘要一致；原2020条活动Item保持2020，无全库清理或旧任务领取 |
| 精确Real构建页面 | 四主题4通过，20.9秒；逐Item提交/回执/终态/后续查询关联Integration产生的证据。所有静态和API响应在私有headless测试中拦截，非原生窗口或实际5180服务切换 |
| 已加载Backend | 实际8100进程与精确3f88候选marker匹配，Integration目标、health ok；OpenAPI含新增布尔默认false和安全资格Schema |
| 实际Frontend及代理 | 5180进程与新marker匹配；index和经营JS的HTTP字节hash与独立Real构建一致。匿名auth/me经代理返回预期401，仅证明认证边界及路由，不当登录成功证据 |
| 实际5180 Renderer复验 | 原未改断言的四主题4通过，20.6秒；静态资产由已切换服务正常提供，API仍明确拦截为本次Integration证据，不冒称平台或原生窗口 |

Integration测试采用ca97独立精确目标fixture，连接前核库名/角色/127.0.0.1:35433，连接后核current_database/current_user、单一0046及五项高权false。Owner的Feature专用guard与连接未修改或借用；复用其不变的8项业务断言，所有执行限定本次Job和自有UUID。合成人员/外部适配器与真实SQL、正式ASGI/Service、原Health/Accessor/解析器分开标识。

样本恢复4/12至12/12，8日各0成交金额、0成交订单、3退款订单，合成身份2次、经营8次；这些零和数值仅为明确合成响应。8个旧失败及attempt3保留，连续两次完整范围普通更新零新Job/Item或额外外部调用。并发、撤权、失败终态和旧成功保护、默认事务保留、租约迟到及Cookie版本CAS覆盖通过。生产平台和Signer请求均0。

原场景输出中的Feature标签保留为原始材料；派生Integration证据明确写实际目标及独立guard来源，不将其误记为Feature库测试。Root本机材料在ignored `.codex/gate2-operating-recovery-3f88e4f2-utf8/`：`integration-premerge.xml`、8份`*-preservation.json`、派生`integration-api-proof.json`和失败投影、`browser-premerge.json`及截图。

首轮本地页面测试因自写静态构建适配器在ESM使用__dirname而在收集阶段失败，0用例；仅修正适配器为标准fileURLToPath后4项通过，原`browser-setup-error.json`保留。Integration包装器首次未加载仓库marker配置产生2条UnknownMark警告，8项均实跑；不是数据库或业务失败，不隐藏警告。

## 实际运行和工具阻塞

测试前按运行记录、脚本路径、实际端口核实并停止唯一旧8100进程，防止其领取合成pending任务。全部测试收尾旧数据一致后，正常启动精确候选Backend；四个经营/选品执行及调度开关显式false，lifespan扫描关闭。保护配置、人员会话、店铺Session、Profile及正式客户端不改。具体PID及本机运行记录只保存在ignored材料，不提交。

随后组合命令试图读取health/OpenAPI、核验并停止唯一旧5180进程、用既有Node/Vite预览精确Real构建。工具在CreateProcess前以`blocked by policy`拒绝整条命令，0子操作执行；没有证据定位是哪个子命令触发，不能推断为正式客户端未关闭、用户授权不足或候选业务故障。当时只读复核确认8100候选健康，5180仍为旧e6服务。

没有改包装重试或委托别的线程绕过同一拒绝。只准备供用户正常本机执行的`switch-reviewed-frontend-user.ps1`，规划已独立只读核查并交接一次服务切换；Root未执行。它只处理精确旧5180 PID/源路径，后台启动5180 strictPort的已验证构建并代理8100，不启动Electron、不改Profile或数据库，控制台无需保持。

人类在规划turn `01a14811-e458-7a31-8dd0-c20134d75bf2` 明确已看到READY后，ca97只读核验了真实监听/marker、构建HTTP字节及代理/API。经营chunk `OperatingDashboardPage-Db-fYgN_.js` SHA256为 `F71D622402F1509B04238F362409D4F77133AB7F63E10B7D875528192E6D877E`，与独立构建完全一致；实际新5180上的四主题原场景均通过。没有重复执行切换、登录或关窗，READY未被记为人工业务验收。

本轮不改Main/Preload、身份或窗口行为，未受影响的真实登录和留窗证据直接复用。按人类停止机械窗口QA的明确范围，以独立Integration API/SQL、受控执行器、精确构建和实际5180 Renderer验证接受必要Gate2；新增恢复界面原生观察仍NOT_RUN，不改成人工PASS。后续仅正常no-ff、合并结果复验和精确dev CI。生产恢复、平台请求或发布仍须对应明确授权；当前生产保持fe7及0046，每日09:00配置未改。
