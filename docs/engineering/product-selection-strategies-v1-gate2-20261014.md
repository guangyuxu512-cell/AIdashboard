# 选品策略 A：Gate 2 与发布交接

## 候选、范围与结论

- Feature：`feat/product-selection-strategies-v1`；Owner81a1，Integrator ca97。
- 最终Candidate：`f348565b4db2cb907d9c55c3fd7c85088a1fe467`；Green起点为
  `3128d6ad1048dfda1240148e863ea0c98eb6247f`。保留完整提交链，不reset/rebase/cherry-pick。
- 2026-10-14用户在当前ca97会话直接确认候选池普通窗口及最大化显示通过，并要求合并发布。
  a75阶段的品牌、策略九列、第二页启停/编辑原位更新已由此前直接人类确认通过，复用不重复。
- 最终候选审查及Gate2B人工验收PASS；合并后复验和精确dev CI须实际通过才标Green。
  本记录不是生产已部署声明；Main须另完成Release Gate、main CI和实际部署核验。

本次交付动态行业/类目及有效父级“全部”、实时/近1/7/30天、品牌、双边元价格、
策略CRUD/CAS/授权和稳定列表、候选池宽度及目标排名分页。保持既有页面、日期有限回退、
候选/来源/补充与事实读取。行业根级直接“全部”编码仍未确认，不开放该未验证选择。
定时配置仅草稿；B服务端执行独立开发、独立Gate和发布，本次不含0045或自动调度。

## 实际集成环境

唯一开发Electron1.0.6，Real `5180 → 8100 → control_center_integration`。
两服务实际源快照均为f348；HTTP转换模块的内联source map内容与候选TS精确一致，
策略表/候选池运行模块包含容器宽度方案，不仅核对分支HEAD。Electron代码相对Green未变，
保留当前Profile、集成人员会话及HuanYu合法StoredSession v6，不复制生产凭据。
Migration单一`20261013_0044`，旧0042/0043和已应用0044不改写；无最终增量迁移。

本次预检28候选/33来源/9run，活动SelectionRun0、到点PC计划0。
经营Job19/Item2820/日事实667，PC计划3/回执1/Task4及ShopSession2均保留。
原生工具截图超时/点击geometry限制如实记录，网页测试不代替原生；最终原生结论来自用户本人。

## 验证与证据边界

| 验证 | 实际结果与边界 |
| --- | --- |
| Owner Gate1 | 最终默认Backend736、前端选品107，lint/typecheck/Real build通过；FeaturePG83与最终target/compatibility27为有重叠的不同组，不相加。平台为合成I/O，非真实取数 |
| ca97最终独立定向 | 精确f348快照Backend135、Frontend71通过；不冒充PG或原生验收 |
| 通用条件 | 类目接口/缓存读取动态root与有序路径，非默认industry5及有效父级前缀有真实只读成功证据；1d/30d分别20/23、上海完整区间有同商品对照；价格20–100/20–40真实筛选集差异，金额按元、单边422；其余保存/回读/CAS/API零平台请求 |
| 真实品牌 | string0知名、1非知名各正式HTTP200/int st0，返回10、排名范围1–1保存1/basic1；不同商品组证明筛选效果，不仅“返回成功” |
| 真实目标页 | 正式v8 run冻结pages[1,15]，page1仅探测一次、page15一次，HTTP200/int st0、total200；只保存官方rank150，非目标页商品零写入；并非完整150–200全部真实采集 |
| 权限/稳定位置 | super按已有资源Team操作，原/无/另一有效Team同key回读200；普通成员与Shop/模块/CAS门禁保留。API启停/编辑真实updated_at、version及列表顺序一致，平台/run/计划增量0；原生第二页/筛选/滚动由用户确认 |
| 刷新与去重 | 已完成正式run的GET刷新和同key重放复用同canonical，category/rank/basic_info实际发送增量0 |

品牌正式run：`38561fbe-a9a1-4844-b0d2-3a5d95d2125c`（0）及
`3feb17a7-a8a0-4ab2-b60b-74530f573a02`（1），上海2026-10-14实时。
目标正式run：`e8221905-d2a2-485e-821f-c1465cd0366a`，同日实时，
product `3847090073610879415`，官方rank150，事实及来源、basic_info和正式API一致。
旧7d run `dae3090a-ceb4-44f3-8bba-4bbf362a5cbf`保留10事实及basic9/1业务600002的partial，
实时run `5b3d3ba4-4d64-4202-888d-50cf8915eccc`保留10事实/basic10，不重复平台请求。

脱敏运行/平台计数证据仅在本机ignored目录；没有Cookie、Token、签名、完整URL或原始敏感响应入Git。
模拟、数据库夹具、只读平台诊断、正式真实run和人工原生确认各自分开，不互相替代。

## 合并复验与Release要求

按`--no-ff`合入dev，冲突仅三份工程治理文档；保持Integration资源与安全事实及已审核B预留范围，
不在dev修业务或Migration。运行代码应与f348字节一致，再完成默认Backend、Frontend完整测试、
lint/typecheck/Real build、实际服务健康/正式查询/Schema检查、diff与秘密匹配计数检查。
精确推送SHA的三项CI全部成功后才交Main；合并SHA与CI链接随后写入发布交接，不预填成功。

合并工作树复验已完成：Backend默认pytest exit0；Frontend lint/typecheck通过，
完整144文件/664测试通过，production Real build通过。930个Backend/Migration/Renderer/Electron
受版本管理文件逐字节对照f348及实际运行快照，差异0。两服务health200；v8目标正式run及
两条v7品牌正式run均succeeded，事实与正式API一致，category/rank/basic_info观测增量各0，
业务计数及HuanYu v6保留。未重复平台采集或原生人工确认。
暂存内容安全审计凭据匹配0、禁止artifact0、冲突0、diff错误0；初轮5个匹配经代码默认值和
无鉴权Origin核实为公开端点登记，不是凭据。当前仅等待精确推送提交的CI，尚未生产部署。

Main发布仅A：从生产已核实单一0043备份并验证可读性，经正式Alembic升到单一0044，
前后端同步，核实实际运行SHA、Backend/Frontend/Signer健康及Real无Mock回退。
保留既有手动采集与每日Asia/Shanghai09:00“仅昨日”计划，不启用B或扩大历史补采。
本次Electron源码未变，不为A重新交付无变化安装包；当前1.0.6及登录Profile保留。

已有v8冻结JSON/事实后必须保留v8兼容Backend Reader、0044Schema和全部事实/失败历史/审计。
若需停止新增功能，用既有管理/执行开关进入只读；不能直接回3128/旧main等不兼容Reader、
不能对有正式数据的库downgrade。Feature降级仅限正式guard核实可重建空目标及排他锁检查。

精确Green后由ca97先核销0044，再激活已审核B0045/down0044；81a1正常merge该精确Green。
B非DDL准备不是自动调度完成，不混入此次Main发布；保留共享stash、7d55与全部未合并成果。
