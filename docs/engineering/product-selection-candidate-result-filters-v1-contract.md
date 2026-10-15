# 候选池筛选、屏蔽与单商品基础补充契约

基线Green9bb64ac；资源7dc8034正常合入；Owner81a1，ca97 Gate2。
唯一0046/down0045，Feature库/8101/4176；本轮无平台请求/生产写入/发布授权。
此文为实施契约，非功能已通过验收。旧42–45、B/PC/Signer/Session及12列视觉保留。

## 身份、查询和发现

屏蔽归属Team-owned Candidate，同团队商品全部来源共同生效，重复desired-state不再审计。
只改配置可处理停用店历史，不取得Session；已删除店沿既有不可见边界。super精确资源操作
按当前真实超级身份与保存Team重新解析、重新查询可见来源；普通Team/Shop/模块范围不变。
ShopSelector clearable可选/defaultfalse，候选池显式开启；清除过滤→page1/清选择/只读查询。

默认仍每Candidate一行最新授权来源。权限、店铺、屏蔽、策略/批次及结果条件先过滤，
再选对应来源/稳定排序/分页。结果范围all/today/today_new/today_known；今天使用上海自然日。
today_new/known表示匹配真实命中事件，不是互斥商品桶；今日先new后known的商品可被两个过滤选中，
total仍商品去重，不将两个命中之和作商品数。精确批次使用该次冻结分类；重放、刷新不造命中。

稳定发现范围使用Team+请求Shop+规范化相对条件（含品牌价格/排名/first-only），不含绝对日期、
页码、备用选择、策略ID/name/version。现有价格转换保证20/20.0等价；旧请求/hash/source_hash不改。
新增成员前同范围已有精确命中为known；可证明无历史的新商品为new；无法证明的旧商品为unknown，
不拿可变last_run_id反推历史。已有合法旧来源只能提供确定的正证据，不能以缺少明细证明未出现。
新创建并完整追踪的商品可使用内部追踪标志作新范围不存在旧命中的证据，旧商品不回填此标志。

## 批次

新增一张append-only canonical rank execution→Observation成员表，unique(run,observation)。
事实/fence/计数/成员同事务；成员冻结new/known/unknown、实际hit_at、范围键及必要榜单快照
（rank/previous/checked/price/first-listed、四video原区间/状态/精度/单位/获取时间）。
题图/title/商家/basic仍当前来源，不复制完整商品详情、原响应、URL或凭据。
精确批次榜单显示/排序取快照，日期/条件取canonical冻结请求；基础补充不改快照。
receipt/reused/定时均解析既有canonical关系，同时核对合法策略归属，不要求用户输入UUID。

Run detail_version旧NULL表示未记录，不回填；新rank接受/首次未执行领取标为1，成功空0成员
仍记录契约已启用。旧批次不能返回伪完整空；API上下文明确not_recorded/recorded与执行状态。
不因原Run随后人工补充成功改写旧partial/失败计数。

## 单商品补充

真实能力是现有basic_info，按钮/服务准确为“更新基础信息”：仅类目、上架日期、差评率/raw unit。
目标product_id保字符串，来自可见Observation的Candidate；Session来自其请求自有Shop，非商家。
不重抓榜、不改四video、榜单checked/metric时间、last_run_id/历史状态，不接手机/collect/竞品。

复用原product_selection_runs与执行器，closed operation_kind=rank/basic_info；旧rank默认及v1–v8/hash不变。
basic专用冻结请求只接受来源ID与submission key，服务端解析Team/Shop/产品/来源；执行前冻结来源版本
与基础版本，短事务领取→事务外既有HTTP/Signer→短事务fenced写入。共用全局3/Shop1/租约/恢复，
不另建attempt队列/扫描器。basic不关联策略/计划，rank列表与策略最近结果排除basic。
basic saved_count=0，补充数量使用其独立单项约束/DTO，不以伪saved=1适配旧CHECK。
同key重放复用原回执，活动同项共用canonical；显式重试是新尝试，不覆盖旧终态。

逐字段latest-attempt state与已保存值/成功时间分开：available才更新；missing/null/invalid及请求失败
保留旧有效值，0正常。无旧成功时间证据不填现在时间。保存白名单字段状态、真实尝试时间、安全code/stage、
实际原类型业务码，未知保持NULL。平台拒绝原因无证据不猜限流/风控/缺Token；认证失效才提示登录。
榜单click invalid与基础失败独立；基础成功不能消除它。列表/详情使用同一短中文状态映射。

## API及迁移实施边界

正式路由（输入只消费对应Pydantic，不接受平台URL/凭据）：

| 路由 | 本轮正式契约 |
| --- | --- |
| GET candidates | 原分页/店铺/search/sort加blocked(false)、result_scope(all/today/today_new/today_known)、strategy_id、receipt_id；SelectionCandidatePage.context明确明细状态/执行/未知商品总数 |
| GET observations/{id} | 可选receipt_id；精确批次读取冻结榜单快照，基础字段仍当前事实；商品/源/团队范围先校验 |
| PATCH observations/{id}/blocked | StrictBool desired-state；同团队商品全源、审计原子提交；重复不追加审计 |
| GET strategies/{id}/batches | 有界分页，真实receipt/canonical/提交时间/原执行状态；visible_item_count按授权商品去重，旧NULL明细时该数量为NULL/not_recorded，不假空成功 |
| POST basic-info-runs | SelectionBasicCreate仅observation_id+submission_key；202已有Run回执，saved_count=0，无策略/计划 |
| GET basic-info-runs/{run_id} | 精确授权basic运行状态，排队/执行/失败/部分成功；不改原rank Run |
| GET observations/{id}/basic-info-run | 当前来源最近canonical basic运行，供刷新/重开恢复进度；没有尝试为null |

策略DTO增加latest_receipt_id，最近结果链接固定该策略真实回执，不用canonical.strategy_id推测关联。
basic_info_status分别暴露三字段latest_attempt_state/last_success_at；旧整体时间不能证明各字段最近年龄，
无逐字段证据保持NULL。旧整体basic_info_retrieved_at与视频时间均保留。结果过滤/策略/批次/店铺/分页
保存在现有路由query；默认最近批次由正式DB批次查询解析，显式选择保存receipt_id，刷新不提交。
策略/批次选项最多一次100项；策略支持服务端搜索与直达ID读取，失败明确显示，不回退全部/Mock。

API延用product-selection模块；新增精确来源屏蔽desired-state与单项basic提交/进度资源，
策略批次列表返回真实receipt/canonical及上海显示时间/原状态/可见数量。输入输出以Pydantic正式schema为准，
前端只消费DTO，不把未实现路由当已有接口。所有读、统计和写执行当前授权，刷新只查DB。

46仅候选屏蔽/追踪属性、一张成员表、Run闭式扩展及Observation最小基础状态/fence；旧事实逐值保留。
生产/Integration恢复保留兼容Reader/Schema/审计并关闭新入口，不能直接旧Reader回退。
downgrade仅精确可重建Feature、锁后无任何新语义：非NULL detail_version即使0成员/失败也拒绝，
basic Run、新成员、屏蔽/审计/基础状态均拒绝，旧B/PC/rank保留。不清库、不改42–45。

生产诊断只有49已保存/46基础完整/3业务拒绝；目标三基础字段尚未取得，旧有效值清空无证据。
st/HTTP/业务消息未留为UNKNOWN，click invalid另算；不伪造旧平台响应夹具。
