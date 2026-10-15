# 四组无用代码清理 Gate 2（2026-10-16）

Owner81a1，Integration ca97；独立Feature `feat/scoped-unused-code-cleanup-v1`，
精确Candidate `1aec1bceef17911ca7067225bd24bfb679fb0c86`，直接父为已核CI成功的
Green `1773a97d27c56512a620337e3259cceabadca2f1`。

规划转交的人类授权为“先发布部署……现在让他清理之前我们说的没用的代码”，
白名单已由规划核准。原选品修复已完成Main21229eff/0046部署及生产核验后，ca97才开始
本独立清理审查。选品发布记录见候选池Gate2文档；本清理没有包含在21229eff中，
没有获得自动生产发布授权。

## 精确范围与独立静态检查

只有4个源码路径加Owner Gate1记录，共5文件：

| 删除 | 独立核验 |
| --- | --- |
| 私有`_LegacyAccessManagementService`及4个仅其使用的import | 对Git原文做Python AST差分，精确移除这一个ClassDef及指定4个import后，与Candidate整个模块AST完全相同；公开AccessManagementService正文逐字相同，其它Actor/Module/Team服务不变 |
| 旧`GenerationResultGrid.vue` | 原组件无导入/注册消费者；Candidate已删除，活跃InstantResultGrid及即时/批量/记录入口保持 |
| `isAssetDownloadCancelled`及孤立ApiError导入 | 文件原文仅这两处删除，其余下载/取消/重试/队列代码逐字相同 |
| `formatOperatingDashboardDateRange` | 仅移除零调用展示助手，日期类型/上海算法/筛选/查询/汇总与采集代码不变 |

ca97独立复核base1773、Candidate1aec、main212、7d55 `03bdc023…`、0106 `b0c272d1…`、
e601 `2e95300d…`的运行源码/测试引用，均没有定义文件之外的调用；Candidate的4个符号均零命中。
Vite仍无组件自动注册，原组件不是动态glob入口；原正式Dependency直接实例化公开类。
未修改他人工作树；保留活跃AI/Mobile仍使用的4个Mutation、公开DTO alias/role定义、
Session验证/查询/useShopLogin实际链、全部Mock/fixture/测试/API/权限/Schema/Migration/依赖。
选品/Shared/app、Electron/Worker/Mobile、部署脚本均无差异。

## 独立候选验证

ca97使用本工作树ignored不可变Git归档与已有相同依赖，不在dev代写代码、不安装依赖，
不启动服务/新端口或Electron、不读取凭据、不连接任何真实数据库/平台/生产。

- Backend既有Access foundation/API/management三文件：22 PASS，4.60秒；
  ASGITransport和内存SQLite/合成Fixture，不冒称PostgreSQL或真实人员登录。
- Frontend下载队列、即时/批量/记录结果、dashboard及FilterBar：6文件27 PASS，13.13秒。
- Frontend完整lint、vue-tsc与Real production build全部PASS，build15.04秒。
- `git diff --check`通过；只有批准5文件，禁止artifact匹配0，无Migration Slot/DB/端口需求。

原jsdom相对图片XHR AggregateError stderr和既有大分包告警如实保留，断言全部通过；
没有借清理修图片、测试或其它代码。未跑无关PG/迁移、真实平台或新视觉验收。
候选仅删除已证实无用实现，不改变已确认布局，故不重复用户Electron视觉验收。
现有885预览、唯一1.0.6/Profile和Integration关闭式执行配置完全不动。

Gate2技术审查PASS，可按正常no-ff集成和合后定向复验，再推精确dev CI；
此阶段不预标Green，也不合main或发布生产。发现新引用/相关回归须退Owner，不能在dev代修。
删除为可追溯Git源码，保留父Green/Feature分支，不涉及数据库、历史数据或Profile恢复。

## 合并与精确CI

待正常集成、合后验证及精确CI后记录；生产发布另行批准，不随选品21229eff重复部署。
