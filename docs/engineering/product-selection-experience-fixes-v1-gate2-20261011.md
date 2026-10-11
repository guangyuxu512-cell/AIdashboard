# 选品五项体验修复 Gate 2 与发布交接

2026-10-11，Integrator ca97，Feature Owner 81a1，Main负责Release Gate和正式生产操作。
本轮仅收口已交付的五项体验修复，不追加平台取数、策略保存、调度、达人或百应功能。

## 版本与审查

Candidate `6e6bfc63f8ee5f3155c134fcb527f44eb9bf4508`，分支
`feat/product-selection-experience-fixes-v1`，Green基线
`a9931a8f8b329bb5e5e79f9e44fd42294ca5d633`。
Gate 1已完成；ca97整体审查ACCEPT，正常no-ff Merge
`5eababba8b0c466f65ad0ec437a1b66e39d96b90`，合并树与Candidate完全一致。
本登记只改变工程记录，最终dev须以推送后成功CI的精确SHA交Main。

用户本轮明确指定该Candidate完成审查、合入dev、CI并交Main部署。
该指令作为集成与交接授权记录，不改写为尚未取得的原生菜单人工验收结果。
Gate 2技术验证及真实读取检查通过；普通/最大化Electron的四级菜单尺寸、滚动和父级全部
未取得独立人工确认，作为Release Gate的明确未覆盖项交Main，不以浏览器测试冒充通过。

## 五项修复与证据

| 项目 | 核验结果与范围 |
| --- | --- |
| 获取结果反馈 | 候选池和策略页常驻结果横幅移除；SelectionWorkspace复用run查询及消息组件，当前显式提交终态只提示一次，跨页仍跟踪，不重播历史；同一Electron实际列表无常驻完成横幅 |
| 区间指标 | 共用选品格式化函数保留两个端点；计数万/亿，确认price按分除100转元后加¥；已有官方同商品展示支持单位换算，不把不同日期的展示比较称为同期数值对账 |
| 差评率 | unit=4比例复用百分比格式，实际已保存0.0006711409395973154在Electron列表显示0.07%；0和缺失由定向用例核验为0.00%和—；数据库原值不变 |
| 店铺类目缓存 | 后端同进程platform/shop隔离24小时、single-flight及deep-copy，展示和正式提交共用；命中/等待者前后复核权限，失败刷新不隐式使用旧树；前端actor/team/shop Query同步24小时和显式刷新 |
| 类目弹层 | 现有NCascader左下优先，沿用Naive/vueuc翻转、视口边界和滚动；4主题×5视口的四级滚动、点击及父级全部拦截E2E通过；原生普通/最大化尺寸人工确认未单独取得 |

缓存只存解析树，不存凭据或授权结果。权限、停用、Session/Signer、日期有限回退、执行租约、事实去重不变。
保留原策略抽屉、页面结构、候选数据日期和失败记录；不改公共控件、主题、Electron、Worker、依赖或锁文件。

## 集成运行与已有真实数据

同一开发Electron窗口“电商 AI 中控台”，Real
`http://127.0.0.1:5180/#/product-selection → http://127.0.0.1:8100 → control_center_integration`，strictPort。
前后端实际源为经Git Object字节核验的精确Candidate快照，不仅核对分支HEAD；合并代码与快照相同。
前端实际加载新格式化函数、Workspace消息及bottom-start，后端OpenAPI实际包含categories的refresh参数。
既有g2_sa_v1_super有效会话读取200、团队上下文不变；未重新登录或改密码/权限。

现有正式run `72f42fff-1996-4d59-9c30-30104f373e63` 的10条真实商品和基础信息用于显示核验，
实际日期2026-10-04～10-10。此次不重新获取榜单/basic_info、不新建运行，不把历史运行算作本轮新取数。
HuanYu首次真实类目读取200，观察到类目调用1、内部Signer调用1，新增榜单和basic_info调用均0。
缓存暖命中、刷新、展示/提交共用及撤权由真实PostgreSQL配合合成平台验证，不宣称原生菜单重复打开次数已测。

原生AX可读取当前列表和0.07%等值；自动捕获超时、坐标几何不可用及缓存元素不可用的限制保留。
额外诊断客户端使用本机既存凭据正常登录返回401，未重试或重置；该请求不作为当前Electron登录证据。
当前Electron已认证读取200与此独立诊断客户端区分记录。

## 验证

| 验证 | 结果 |
| --- | --- |
| ca97候选Backend定向 | 99 PASS，缓存、connector、mapping、API/source及Douyin请求回归 |
| ca97候选Frontend | lint、typecheck、Real production build PASS；13文件89项unit PASS |
| ca97 Integration PostgreSQL | 43 PASS、4 deselected；真实Integration库、合成平台，排除Schema downgrade及3个需空Feature库重新指定唯一超级账号的既有用例 |
| Owner Feature PostgreSQL | 独立Feature空库46 PASS、1 downgrade deselected，包含上述3个空库用例；不称为ca97独立46项 |
| ca97浏览器Real契约E2E | 3 PASS；全部正式HTTP拦截，覆盖跨页一次反馈、无历史重播、4主题/5视口菜单；不当作Electron或平台调用证据 |
| 合并后复验 | 实际ca97合并代码Backend同组99 PASS；Frontend lint、typecheck、13文件89项unit及Real production build再次全部PASS；业务树与Candidate相同 |
| 字节和安全 | 1493 tracked blobs一致，仅11项仓库声明CMD行尾转换；本地敏感值匹配0、禁入文件0、production Mock marker匹配0、diff-check PASS |

PostgreSQL首轮39 PASS/7 FAIL的现场记录保留：旧执行器抢占合成pending任务，以及3项空库唯一超级账号夹具与已有集成账号冲突。
停止已核验旧执行器后，43项共享库适用用例全部通过；不改候选/测试、不提权、不撤销已有超级账号。
合成夹具残留0，正式10条事实和失败历史保留。既有TestClient及大chunk警告保留，不改依赖消除警告。
本机脚本、日志、截图、PID、配置及构建产物均ignored，验收证据不含凭据。

## Migration与Main交接

无新Schema/Migration，单一Head保持`20261010_0043`，0042/0043原文件不变，不占新Slot。
Feature库retained，未复制Integration账号、事实或Session到生产。
本轮前后端需同步发布类目refresh和缓存契约；桌面壳未改，不另打安装包。

精确dev CI成功后由Main按现有Release Gate核对main完整差异、当前生产/存储/0043、可读备份及上述未覆盖项，
再正常合入Green dev、推送main并等待对应CI和单次自动Deploy。
不将合并或CI成功单独写为DEPLOYED；生产实际SHA、服务健康、Real显示和缓存授权验收后由正式发布者登记。
不触发经营采集或付费生图，不改变生产每日09:00配置，不为本轮显示重复请求榜单。
失败在共享历史正常revert；无数据库回退或清表，保留事实/run及0043。
