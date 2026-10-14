# 候选池筛选／屏蔽／单商品基础信息：资源与最小方向放行

Owner81a1，Integration ca97，规划聊天确认产品范围，Main只接合格Release。
已回读直接人类原需求与设计批准01a13b3b-f49a、前一方案01a13b34-48f1及新增生产问题/
分配授权01a13b7e-ff39、01a13b80-979a。本次独立Feature，不加入已经完成的A/B发布或7d55商品数据页。
资源与技术方向接受不等于Gate1/2、Green或立即生产发布通过。

## 已核验基线与资源（2026-10-15）

| 项目 | 正式放行 |
| --- | --- |
| 基线 | 精确Green `9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`，CI38597874343三项success；远端仍精确相同，不从ca97纯治理或main起Feature |
| Worktree/分支 | `C:\Users\Administrator\.codex\worktrees\81a1\中控台`；由Owner从Green正常创建 `feat/product-selection-candidate-result-filters-v1`，保留Ops1677、B7db、全部成果和共享stash239a68ca |
| Feature DB | 串行重新分配已登记retained `control_center_feat_product_selection`；当前单一`20261013_0045`，Owner/role `control_center_dev_user`，八项业务计数0、活动Run0、其它连接0；不清库、不创建新库/权限，不复制生产或Integration会话 |
| 连接 | 复用当前受保护Feature配置与已登记严格35433隧道；已新鲜连接成功，Role无SUPERUSER/CREATEDB/CREATEROLE；不在聊天/Git/日志输出凭据，不改其它环境配置 |
| 端口 | 复用Feature Backend8101/Frontend4176，Vite strictPort，现场均空闲；禁止占8100/5180或另开Electron/动Profile |
| 唯一Slot | 新`20261015_0046_product_selection_candidate_result_filters_v1`，revision `20261015_0046`，down精确`20261013_0045`，`active`；实际目录/登记最高45且45已released，未借槽、不改已应用42–45 |

Owner先建分支、正常merge本次资源治理提交（仅文档/规则，非新Green）以同步自己分支的权威登记，
重新读完整适用规则，再编写/在登记Feature库应用46及PG测试。ca97不编写Migration或代修业务。
本阶段仅合成平台I/O+Feature真实PG，不发真实平台请求，不连接Integration/生产开发；
真实Integration行为在合格精确Candidate后另由ca97安排，不将生产拒绝样本冒充原平台响应。

## 接受的最小实施方向及必守修正

1. 清除×只扩现有ShopSelector可选透传clearable；CandidatePool开启、策略必选默认不变，清除移除过滤条件。
   共享透传最终冻结由81a1在本Feature单独实现；7d55收到协调已撤回重复增强并组合现有查询/选择能力。
   不要求其反复恢复或另交共享技术片段，不重复写组件/引入未验商品数据页，两项其余开发不互等。
2. 屏蔽在现有Team-owned Candidate身份加最小状态/时间/人员，所有来源一致；复用audit_logs，
   行锁/desired-state幂等，同状态不重复审计。先当前权限/可见来源，再资源Team重验；普通成员范围不扩大。
   屏蔽/恢复是纯DB配置，不取得Session/Signer、不因Shop停用拒绝关闭；已删除Shop仍按现有读取边界拒绝。
   super直接操作已有候选/精确来源时若按资源Team解析，必须作为关闭式领域例外记录到权限契约，
   验证真实super/有效Team/Shop，不伪Team、不选默认Team或新增Membership。其它写边界不变。
3. 只新增一张本业务append-only canonical→Observation结果关联，unique(canonical,observation)，
   事实、fence、计数及membership同短事务提交；复用receipt/canonical和完整策略关系。
   旧NULL明细版本=未记录，不反推；新tracked成功空/失败零item与旧未记录明确分开。
   接受Owner补充的同表最小闭式榜单快照：真实rank/必要previous/checked、价格带、平台首次上榜标记、
   四视频字段的状态/原精度区间/类型单位与取数时间。不是完整详情或任意response快照；无URL/凭据。
   精确批次的本次排名/指标及排序读取此不可变快照，不用后来更新的Observation伪装历史本次。
   图片/标题/商家和基础信息复用当前来源，单项补充不改旧快照/Run；旧未记录依旧不可反推。
4. 来源发现范围为Team+请求Shop+原相对业务条件，不含实际日期/分页/备用选择/策略UUID/版本。
   **新key要复用已确认价格规范化**，20/20.0等同；不得修改既有rank v1–v8/hash/source_scope_hash。
   新/再次命中是进入同条件范围，不是平台首次上榜或策略名称首次出现；旧明确正证据可known，
   无充分证据为unknown，不填new或造旧batch。本次unknown已记录后，后续可证known。
5. 今日按真实membership.hit_at的上海自然日；重放、刷新、receipt不造第二次命中。
   **保留原默认每Candidate一行最新可见来源**，不是仅Observation去重而增加重复商品行；
   先授权/Shop/屏蔽/策略/批次/结果范围，再复用最新来源选择、稳定去重/排序/分页。
   同一商品今日先new再known可以满足两种事件筛选；筛选“今日新进入”不能额外限制为“最后一次仍new”，
   后续命中不抹去当天真实首次进入事件。默认今日结果可取最近命中，明确批次仍取该批冻结状态。
   “互斥及分类之和”只能针对命中记录，
   不能把两次命中之和当分页商品数。对应过滤展示其匹配冻结状态，未知覆盖如实说明，
   不用Run.saved_count代替当前可见商品total。
6. 单商品只接已有basic_info：准确按钮“更新基础信息”；目标ID来自已可见候选，认证请求店铺
   来自Observation，不是商品商家。只更新类目、差评率/单位、上架日期；不重跑榜、不更新视频四项/metric时间，
   不接资料collect/竞品/手机，不通过整体available=true误开未接功能。
7. 接受关闭式复用已有Run/Executor/shared容量3与Shop1/lease/fence：rank/basic_info分支，
   basic专用冻结snapshot/POST只接受来源ID+submission key，服务端定权限/身份/来源版本。
   不能伪造saved=1以满足旧CHECK；最小按operation区分DTO/约束/claim，原rank/hash/PC/定时不变。
   basic不挂策略/计划、不污染rank列表或策略最近结果；新attempt终态不改原Run历史结果。
8. 复用当前事实落库，最小typed基础状态/版本fence：字段available才改值，失败保旧事实/真实成功时间；
   新尝试字段状态/安全码/原类型业务码/最近尝试明确，旧缺证据unknown且不生成时间。
   自动补充和单项调用共用；重复/活动复用/跨权限/错商品/失租约/旧rank及迟到结果保护须PG覆盖。
   超时、认证、签名、平台拒绝、字段不完整、未知使用短中文映射，不猜风控/限流或一律要求登录。
9. Schema仅Candidate屏蔽、一个membership、现有Run关闭式扩展及Observation最小状态/fence，
   不新增队列/扫描器/通知框架。46 downgrade仅精确可重建Feature、加锁后无任何新语义：
   **非NULL明细版本即使0item、basic Run、新状态/屏蔽审计均须拒绝**；旧B/PC/rank数据逐值保留。
   生产/Integration不降级清历史，恢复保留兼容Reader/Schema/审计并关新入口。

## 交付与职责

Owner实现和Gate1：合成响应/真PG分开，定向覆盖以上边界与Real不可用功能，按项目要求测试/质量/Real build，
交精确Candidate、Schema/契约/回滚和未覆盖项。不得把技术方向放行或测试可收集当通过。
ca97审查精确候选、Gate2/对应人工确认；业务缺口退Owner，不在dev代开发。
不重验未变A/B、不为本轮开发触发生产取数；Green及新任务发布条件满足后才交Main。

生产只读诊断另见 `product-selection-basic-info-production-diagnosis-20261015.md`。
它是已有DB/安全日志状态证据，不是完整原响应或一次新平台验证。
