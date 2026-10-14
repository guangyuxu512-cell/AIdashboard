# 候选池结果与基础信息 Gate 2 集成记录

ca97独立审查精确Candidate `51852cc6ab46bdc96533ee2f84de7cc9c1880714`。
技术与Integration数据库/API验证通过；原生Electron与真实平台基础更新尚未完成，Gate2整体保持进行中。
此Feature未获生产发布授权，生产维持已发布B `382ca92ee1f415e0e1a4269de6b9a02c382e114d`/0045。

## 候选与技术检查

Owner81a1，分支feat/product-selection-candidate-result-filters-v1，基线为精确Green
`9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`。最终51852cc6只在功能提交df3d4cb后整理迁移测试EOF。
ca97使用本地ignored不可变Git归档，不把Owner工作目录或治理HEAD当运行版本。

独立检查覆盖当前授权重验、Team商品全来源屏蔽、desired-state原子审计、canonical批次关联和冻结排名，
今日匹配命中后商品去重、旧明细未知、价格规范化发现键，以及basic操作共用原Run/Executor/容量/租约fence。
basic仅更新已确认基础字段，saved_count=0、无策略/计划，保留旧rank状态与视频事实。
Migration46在线预检旧约束名称，降级在DDL前限制精确可重建Feature并拒绝任何新语义。

Backend独立默认807项通过，新增相关纯逻辑14项另行通过、不叠加统计；Frontend选品/Selector/Audit
17文件124项通过，lint/typecheck/Real build通过。仅既有httpx弃用与大于500kB分包警告。
Owner66个Feature PG场景和四主题API拦截截图属于Gate1证据，未当作原生或平台成功。
Electron源码与现有ce3/1.0.6壳相同，无新安装包需求。
候选内容及本地敏感值检查仅输出计数：敏感匹配0、禁止artifact0、冲突0、diff check错误0；
锁定依赖及42–45旧迁移相对Green保持不变。

## 集成迁移与运行版本

复用control_center_integration/control_center_dev_user及既有严格35433连接；未改凭据、Feature或生产。
pre46受保护custom dump为556835字节，pg_restore list343项可读，SHA256
`3185e874ea83c4bc689e7a801323ac5842814d39b72851b225614b6b5ae19d16`。
正式Alembic从候选归档执行45→单一`20261015_0046`，Migration文件SHA256
`F87B00229065BADC506CE3BE38E59AB9E7B2DF1833918941D8F4833F924C2F9C`。
12张原业务表全部旧字段的逐行摘要/计数保持，HuanYu仍valid v6；42–45文件不改。

只停止经PID/命令/监听核对的旧8100/5180服务。新Backend/Frontend实际来自精确51852cc6归档，
8100/5180 strictPort，Real。/health返回ok，OpenAPI正式blocked/basic路由和新Renderer已核对。
本阶段lifespan关闭、手动执行/定时false，并在测试入口阻止选品平台HTTP；非生产Signer8787原配置保留。

## 正式 API 与数据库夹具

通过受保护既有凭据及正常/auth/login建立独立HTTP会话，实际服务端确认g2_sa_v1_super为超级账号，
未注入Token或制造Electron登录状态。场景使用专用G2-CandidateResults A/B（合成验收）、
商品9999000046001001、策略G2-CandidateResults 筛选验收（合成）。
真实Integration数据库和正式API参与，平台适配器是合成响应，实际平台请求0。

| 场景 | 实际结果 |
| --- | --- |
| 全部与今日结果 | 每商品一行，店铺A取最近排名17；不同店铺来源不增加重复商品行 |
| 今日新发现与今日已发现 | 同一商品先新11再已发现17，两类事件均可读，不以最后命中覆盖当天首次事件 |
| 精确批次 | 首次回执排名11、后次17，列表/详情一致；真实回执/canonical可见数量均1 |
| 屏蔽与恢复 | 超级账号无Team头正常操作；全Team商品来源共同隐藏，重复true仅一次审计，恢复可见 |
| 单项基础补充 | 同key回放及活动合并，无重复执行；完成saved0/补充1，不挂策略/计划 |
| 失败与字段缺失 | 合成业务拒绝保留旧值及成功时间；随后真实数值0有效、missing/null保留已有类别和日期 |
| 历史事实 | 基础更新不改rank、video、metric时间、last_run_id或原rank partial/计数 |

首批回执`8709d96d-11f1-48ee-b91a-cbb04134638c`、后批
`20dad5de-3a20-452a-b995-7a8944c020c3`，来源
`b1b9710b-044a-4257-98e5-48274cc2a022`。这些ID仅是本候选集成夹具，不能用于声称平台取数成功。
全部专用Run已终态，原PC/经营/店铺Session数据保持。诊断脚本、JSON、日志、备份、截图及运行PID仅存ignored目录。

## 原生验收与下一步

现场核对开发Electron已退出，仅正式客户端可见；保留正式窗口与原Profile，不启动第二实例。
已一次性请求用户正常关闭正式客户端。之后ca97用已准备入口打开唯一匹配开发1.0.6，复用人员会话，
在候选池集中确认清除请求店铺、四结果范围、真实策略/批次、屏蔽恢复及基础更新状态。
未改A/B页面和先前人工结果不重复验收。原生输入或截图限制须按真实错误记录，不使用网页截图代替。

真实平台单项样本仍需受控正式队列/当前Integration合法Session与隔离Signer核验；
不复用生产Cookie，不把上述合成数据或历史成功当本候选平台闭环。
只有后续必要验收通过后才正常no-ff合dev、合后复验、精确CI；本轮不自动推进main/生产。
生产3848213119470010668历史业务拒绝的HTTP/st未知与独立click异常继续保留，未被此次准备解决。
