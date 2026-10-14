# 生产选品基础信息缺失：只读诊断（2026-10-15）

授权来源：规划直接人类生产截图与正式分配；只读既有记录，不发平台请求/重跑/重试/改配置或数据。
实际production `382ca92ee1f415e0e1a4269de6b9a02c382e114d`，DB `control_center_prod`/单一0045；
沿既有strict-host-key SSH及生产最小应用角色，事务READ ONLY。业务写入/平台请求/配置变更均0。

## 正式运行记录

Run `0d552e4f-b609-469b-bf2c-549724ba8dd1`，请求店铺HuanYu
`66a0ccc6-88cb-44bb-9c4c-f4a43fe07698`，Team `d319c264-f572-4dc5-afe6-c6f9711a394c`，无策略。
接受上海2026-10-15 01:35:54，开始01:35:55，结束01:36:48，状态partial/completed。
条件为短视频/实时10-15单日、行业7、类目1000001142/1000001143、品牌-1、不限价、首次上榜筛选、
官方rank150～200；v8冻结pages[1,15,16,17,18,19,20]，primary无备用。

| 指标 | 既有记录 |
| --- | ---: |
| 结果/保存 | 49 / 49 |
| 基础信息完整/失败 | 46 / 3 |
| 总安全错误 | PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE / basic_info |
| 三个失败来源共同分类 | DOUYIN_SELECTION_BUSINESS_REJECTED / basic_info_request |

49是正式运行过滤后的结果和保存数量，不是原始全榜总数；不得把rank区间或页号推成丢失数量。

## 指定商品3848213119470010668

商品商家富耀易购（平台商家237477956），不是请求认证店铺HuanYu。
仅一条Team身份Candidate `d1a78eda-ec8c-40e0-99b0-07fb05af897d`，一条Observation
`9c6bd035-c252-46fa-8043-82815072614f`；官方rank198，实际实时范围10-15。
首次入库/指标检查上海01:36:38.762976，最近尝试01:36:48.336229；
category_path/first_on_shelf_date/bad_comment_rate均NULL，basic_info_retrieved_at=NULL，
last_error_code=`DOUYIN_SELECTION_BUSINESS_REJECTED`，stage=`basic_info_request`。

这属于**首次基础接口请求业务拒绝后未补齐**。没有更早候选/来源/完整补充值被清空的记录证据；
当前Service只写available字段、失败仅写安全状态，不能从截图说“原有效数据被丢失”。
不是合法成功空数据、不是这条记录的字段部分解析错误，也不是已证明的登录失效或平台风控/限流。

另外，四个榜单指标中pay_amt/pay_combo_cnt/video_cnt为available，product_click_cnt为invalid。
该榜单点击指标无可确认值，**独立于基础接口拒绝**。现无原字段结构证据，不断言具体解析缺陷；
只补basic_info不会修复点击指标或刷新成交/视频数据，仍需保留—和未知边界。

## 能解释与仍未知的原因

当前失败持久化只保留受限错误类/stage；该Run.platform_business_code=NULL，
Observation也没有逐项业务码/业务消息/HTTP状态字段。读取已有界定时间段日志并按目标或Run筛到53行，
没有能证明本条具体HTTP/st/业务消息的白名单信息；不输出/保存原日志、完整URL、Cookie、Token或响应。
因此已知“基础接口业务拒绝”，**具体平台业务码与拒绝原因UNKNOWN**，不补造600002等旧样本码。
请求日志按当前契约只记录路由/状态/耗时/身份/安全错码，不承诺记录平台原响应。

缺少的是本条当次HTTP和实际业务码/安全失败字段证据，不是用户密码或完整cURL。
本次不追加请求，不能通过重新登录或批量取榜伪装为诊断完成；未来被明确授权的单项尝试应保存最小安全证据。

## 已交Owner的最小处理与本次边界

81a1新Feature接单商品“更新基础信息”，复用已确认basic_info与StoredSession；
新增准确最新尝试/字段状态和短中文“平台拒绝获取基础信息（具体原因未记录）”，原类型实际业务码在以后取得时保留。
旧三项未知不填0，不改原Run49/46/3或partial历史；失败保已保存事实，成功只回读对应基础字段。
product_click_cnt invalid不被该按钮冒称已修好，未知原结构不猜接口/单位。
此证据仅DB/现有安全日志状态，合成测试不得冒充本条真实响应。
诊断前后候选49/来源49/Run1计数保持，未触碰生产Session或集成Profile。
