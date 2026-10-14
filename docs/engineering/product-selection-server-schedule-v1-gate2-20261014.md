# 选品策略 B 服务端定时 Gate 2（进行中）

Owner81a1 / Integration ca97。精确候选
`7db6578e67225efe8b77830712ccdbc72d6803cb`，分支
`feat/product-selection-server-schedule-v1`，基于A精确Green
`f5d4866459acf3e29459a9920c03c1e9118a8839`正常合入依赖。
7db相对完整运行候选6e0ad128仅两处契约记录订正，代码、Schema及测试字节一致。
**技术审查接受；Gate 2尚未通过，未合dev/未发布B。**

## 独立技术审查与证据边界

ca97复核Schedule与原Run职责、短事务/CAS/当前权限/Shop/lease、确定性occurrence回执、
全局默认3/同店同有效策略至多1、旧PC查询隔离及42/43/44/45迁移文件不变。
候选凭据匹配0、临时文件0、diff错误0；未在dev代修业务或Migration。
Backend定向153通过；Frontend14文件120通过、lint/typecheck/Real build通过。
这些与Owner Feature PostgreSQL证据分开，不把本地纯测试或合成平台响应认定为真实取数。

Owner在登记Feature库单一0045完成一次100计划合成验证及队列/权限/PC兼容/迁移保留边界；
ca97独立只读核实八项计数0与最小应用角色。这不是100次真实请求或自然timer证据。

## 匹配Integration准备与正式0045

受保护的Integration pre0045 dump549842字节，SHA256
`0be01e546e17556fec0f98543e252378874cc57256545072694525fce754f871`，
pg_restore list339项可读。本地dump仅Administrator/SYSTEM访问且ignored，不导出生产会话。
正常停止已核实归属的8100，再从精确7db归档执行正式Alembic0044→单一0045；
旧候选28/来源33/Run9、经营19Job/2820Item/667事实、PC3计划/1审计/4Task、2Session均保留，
逐行摘要及HuanYu valid v6相同，无平台请求、无业务写入。生产未操作。

匹配7db的Backend8100/Frontend5180 strictPort已启动。正式HTTP/health健康，
StrategyDrawer实际服务source map与候选源字节一致，不只根据分支HEAD判断。
原唯一1.0.6 Electron98292、Profile和已登录g2_sa_v1_super保持；原生只读状态已确认URL为5180、
该账号及Real已有候选数据。窗口app注册旧路径与真实exe不同，以返回窗口句柄4266782/
当前PID98292核对为同一实例，不以旧路径别名冒充新版壳或另开实例。

## 正式API配置验证（不等于执行）

正常认证使用既有受保护Integration凭据，只用本次HTTP Cookie jar；正常登出该jar，
不注入Token或改变Electron登录。通过正式API创建两条专用G2-Selection-B策略：

- 每3小时配置：严格下一上海整点，N保存/回读；0被422拒绝，旧版本409拒绝。
- 无团队超级账号编辑已有策略/启停成功，后台按保存Team重新授权；普通权限规则不改变。
- 编辑名称/条件保持已有cadence，停用清空next，重启用生成未来next。
- daily配置按Asia/Shanghai保存回读，暂时停用。

只新增2策略、2server计划；Run/事实/PC审计/经营/Session增量均0，
类目/榜单/basic_info HTTP增量0，原PC/A业务行摘要保留。

## 一次自然到点及原生验收（待完成）

通过正式保存API，将专用策略`eb1d3e01-75c5-4621-8391-533fdbf43c12`
关联计划`1bd19adc-10f3-46ed-a965-20dd7f09d2f8`设置为2026-10-14北京时间13:54。
仅该一条server计划启用，未来10分钟PC计划无冲突、无活动选品Run；PC Worker当前在线0。
保留原2条pending PC Task、不创建假Device/Skill。HuanYu使用Integration既有v6 Session和8787
本地隔离Signer，Signer健康；仅实时已确认类目rank1～1样本，不重复A品牌或整榜。
临时只开启Integration的选品执行/调度，经营执行关闭；原完整app lifespan、原10秒扫描/3执行器，
不手调trigger/executor或伪造到点/平台响应。此时尚未产生新Run或平台请求。

Computer Use可读取原生窗口文字，但点击返回`coordinate input geometry is unavailable`，
重新选择/激活后的截图返回`FrameArrived timed out: timed out waiting on channel`。
不使用网页截图替代原生确认；已请求用户正常关闭该开发Electron以核对客户端关闭仍执行，
之后复用同一Profile恢复并只补B新增定时控件/结果尺寸，不重复已通过A候选池或整体视觉。

尚需：自然ScheduleRun/理论及实际时刻、真实Run/来源/basic_info/API/UI一致、
关闭Electron/PC离线仍执行、重复扫描与停用无新增事件、临时开关恢复。
上述完成前不标Gate 2 PASS、不合B dev/main或发布。

## 后续自然执行实测（后台项通过，原生项仍待）

原扫描器实际在13:54:04.931接受理论13:54的occurrence，ScheduleRun
`48f8fcf4-5c80-4e79-a66b-45c3f94278c0`关联正式Run
`d205fabc-c68f-47e6-a768-279d537f56c5`。13:54:06.029开始、13:54:11.908结束，
状态succeeded、result/saved/supplemented各1、补充失败0、无错误；下一次为次日13:54。
category、rank、basic_info各仅一次真实HTTP，均200及整数业务码0。
平台第一页合法返回10条，正式rank1～1过滤只入一条，不以10条响应冒称保存10件。

商品`3846580557572080245`、官方rank1、实际实时2026-10-14；Observation
`f539713b-e369-4b31-b3b2-3cd2737f9fdd`的last_run、商品身份/排名/日期在DB与正式API逐值一致。
原28商品身份保持，新增来源一条为34、Run总10、ScheduleRun总2、原PC Task仍4；
经营及Session未写，保留原9Run和正式事实/失败历史。
本次准备/观察脚本字段核对问题仅在本地ignored测试助手内修正，没有修改候选业务或Migration。

后续重复自然扫描及正式API刷新均未产生额外Run/审计/平台请求。通过正式启停API停用专用策略后
next=null、活动选品0、server启用0；继续扫描仍1/1/1 HTTP和同一审计，随后正常停止本测试Backend，
从相同7db源恢复两自动开关false及健康8100，保留同一5180/Electron/Profile、全部记录和事实。

**该触发时Electron98292仍打开；虽PC Worker在线0，不能写成“关闭客户端已通过”。**
用户关闭操作尚未回传。Gate2剩余仅该独立性现场及B新增N/daily/下次时间/结果的原生確認，
不重复A普通/最大化候选池确认。当前环境已准备，用户无需服务配置、登录、凭据或重新取榜。

## A与B发布边界

A精确Green f5及main48ca680两条CI成功；首次Deploy38505980435失败，
旧生产实际0102dd6d/单一0043和09:00配置已恢复健康。A尚未部署。
独立builder只无凭据smoke通过，正式builder选择入口最小工程修复尚待人类范围授权；
不盲重跑、不将B混入A Release，也不将恢复稳定生产写成A新版部署成功。

## 客户端关闭独立性与原Profile恢复（2026-10-14后续）

用户明确报告已退出并授权继续。只读仍看到原98292及窗口4266782；Computer Use重新选择
同一窗口后正常Alt+F4关闭，不强杀、不清Profile。随后实际进程数量0并记录新鲜时间戳。
对原专用策略用正式CAS保存未来每日17:11，保存零Run/审计/平台；只开该一条server计划，
原完整lifespan/10秒scanner/3worker。执行前后开发主进程0、PC Worker0、无其他选品活动。

理论17:11，实际17:11:04.987960接受，ScheduleRun
`6464b505-c517-48de-808b-67db54b8123c`→Run
`206d4cfc-b370-4257-8f4b-b381a76b844a`；17:11:05.654开始/17:11:11.365结束succeeded。
真实category/rank/basic_info各1次HTTP200/整数st0，保存补充各1、失败0；依然只取rank1。
商品3846580557572080245/实际2026-10-14/rank1/来源f539713b在DB和正式API逐值一致。
复用已有身份/来源，不重复新增：身份28/来源34，Run11/审计3，旧PC Task4及2pending保留。

正常停用后next=null、server启用0、活动Run0，后续扫描与查询不新增审计/Run/平台请求；
恢复相同候选Backend两个自动配置false并保持健康8100/严格5180。
准备只读原生预览时，按正式启用API生成未来10月15日17:11，零Run/审计；全局执行仍false，
不是新自动取数授权，也不把未来next当作已执行。N=3专用策略保持原保存配置。

按正常开发入口复用已核验同一SDK/ce3源码（与B Electron字节一致）/1.0.6及原
`Siyu AI Control Center` Profile，唯一新PID19984、窗口17303688；Backend56816/Frontend87772。
原生只读确认5180/#/shops与G2-SA-V1 Super Account可见，无需再登录。
点击geometry缺失、截图FrameArrived超时限制仍在，不用网页截图代替。
已给用户一次集中清单：G2-Selection-B两专用策略N3/daily17:11/次日next/真实成功1件、
普通与最大化新增控件不遮挡，只看/取消不再取榜；A旧整体视觉不重验。
**B后端真实独立性已通过，原生清单尚未回传，Gate2仍PARTIAL/未合B dev或发布。**

同一人类turn已明确授权A最小builder工程修复，不改业务/依赖/Migration。
唯一Owner81a1/独立feat/production-buildx-builder-selection-v1，Main统筹Release，7d55未切支或改文件。
OwnerDraft1677fd3只4工程文件，Windows权限/ln语义不能替代Linux；被拒临时cleanup目标未执行且不绕过。
正常Draft PR13触发现有Ubuntu CI38542431178，Gate1待完整通过，ca97同步静态审查；
B资源窗口结束已回Main，正式构建仍须工程Gate2/精确Green CI，不据授权/Draft直接部署。
