# 商品数据前端 V1：资源放行（非业务/发布通过）

Owner 7d55，Integration ca97；规划聊天直接人类确认前端方向并要求正式分配，Main仅负责未来合格Release部署。
本阶段仅独立商品数据前端及源码/契约只读盘点，不与81a1候选池修复合并，不接真实后台/平台/调度/通知。

## 2026年10月17日当前资源和下一步

原UI候选c30117facfa518456d8362cfa603be86315b4611及既有材料保留；Owner在原Feature正常同步
精确Green08176d9c5cdbea50114eb0656975a209205761bd，已交完整af6b737281c16e469fdc6300f80cdfb40cb5c981，
整树与预演一致且商品26/Shared未变；新148项及lint/type/Real build证据接收，不使用ca97未推治理6b326。
原独立69单测和18项静态浏览器通过范围复用，DEV-only错误恢复样本已在正确DEV环境补1PASS/6.8秒，
不删除原模式失败报告或当作原生通过。匹配完整Candidate及新增UI人工确认尚待，禁止独立发布Mock商品页。

Owner仍只有4177前端资源，当前未监听，不因此启动新Backend或占用新端口。ca97技术检查曾用既有5180
严格端口的c301归档DEV Mock；现5180为独立登录提示e6 Real，af6归档已准备、尚未在原生加载。
8100原进程和数据库保持，正式1.0.8/生产Origin/Profile未动，没有开发Electron。
原生切换如确实需要用户操作，由规划集中说明一次最小操作；不让用户在生产验收未发布商品页。

真实接入本阶段只有最小契约盘点权限，没有DB连接/写入、DDL、平台请求、采集或清理授权。
0046已经released，当前没有active Slot；本任务未分配0047、Feature DB或Backend端口。
Owner需明确商品/指标事实职责、完整条件和日期粒度、版本原子发布及保留、单位精度、服务端权限筛选排序分页、
失败/部分覆盖与现有执行器复用方案，再申请独立Feature资源，不借旧Availability、Integration或生产库开发。
既有74指标单页响应可支持17项字段代码和原单位，不能证明金额/比例换算、全量覆盖或历史滚动更新已经实现。
Owner的真实接入修订草稿已完成技术方向审核：明确商品/事实/切片/滚动序列键分离、全页与逐项覆盖分离、
原子代发布及失败保旧、单位不明不开放百分比筛选、事实Shop授权与运行回执权限分开。
该审核不是API/Schema或执行放行。首版切片覆盖、自定义日期交付顺序、分组协作等业务选择仍待后续收口；
金额/比例尺度等技术证据优先复用已有材料，不把下一阶段写成“等待数据库”或默许45切片/店和自动清理。

## 2026-10-16 接回Gate2与最新基线

ca97已直接回读规划人类turn01a14160-06e9-7183-8ad5-13d9d4e6b4e4、消息
01a14160-079e-7f83-a976-e2d9233bf306：“商品数据先推进”。本轮恢复原UI_ONLY验收，
不将商品数据发布生产，不混生产选品21229eff或尚未另获发布授权的清理。

当前精确Green为5a18bd0390cb4b8cbed637d412f7482cefff3f36，CI38793358927三Job success；
ca97治理HEAD不是Green。旧完整候选03bdc0238465bcad79701af02c04b9811f96a51b保留，
其共享消费03d336双父为b2ccc2f/141fec65，与当前Green的merge-base为纯共享1a8078。
ca97只读merge-tree确认正规合并无冲突，已交Owner在原分支正常no-ff同步精确Green，
再封存新完整Candidate与匹配增量验证；不rebase/reset或在dev代修，不重做已通过Radio返修。
继承最新Green是基线同步，不把清理单独再合一次或借机发布生产。

7d55仍只有原4177 Mock/strictPort资源，已恢复且仍归Owner；无Backend/DB/Slot/Signer或平台
调用资源。最新完整b9fa5717已正常同步精确Green，ca97独立51项/lint/type/Real build及13blob通过。
用户回复“已退出”且客户端进程0后，ca97将5180切到该归档，Real边界浏览器1项PASS后切明确Mock，
正常打开原Profile唯一1.0.6开发Electron并置前；8100原进程/0046/Session及生产均不动。
原生AX已确认5180/#/shops和Mock管理员预览；截图FrameArrived超时、导航点击geometry不可用，
已停止原生输入，请用户仅从“数据中心→商品数据”进入。未声称商品数据页已现场确认或Gate2B通过，
不以网页截图、构建或启动替代原生验收，不另开实例或更换Profile。

Owner只读契约盘点并行继续：源码/旧项目/既有请求层与样本响应的字段/单位/筛选/排序/近1/7/30/
完整分页逐项列证据。不得执行cURL、追加真实请求或猜自定义日期；“最新+上一版”尚非已批准Schema，
无新迁移/调度/数据库权限。盘点和UI候选准备互不阻塞，前端验收通过也不等于真实接入完成。
以下9bb/旧端口现场等为最初分配阶段历史，当前以本节和后续精确Gate2记录为准。

## 基线与工作树

- 最新精确Green `9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`，CI38597874343三项success；
  生产B382/0045已完成，不再等待A/B，不使用ca97之后的纯治理HEAD。
- 正规既有Worktree `C:\Users\Administrator\.codex\worktrees\7d55\中控台`，现场仍干净detached3128，
  由Owner正常从精确Green建立 `feat/shop-product-data-frontend-v1`，保留旧归档/分支/stash；
  必须重新阅读新分支完整适用规则，不在旧3128编码，不改main/dev。
- 原归档 `7d55-archive-20261013-1baaab5b`保持，不删除或再次重建Worktree。

## 唯一前端运行资源

登记独立 `127.0.0.1:4177`，Vite显式 `--port 4177 --strictPort`；现场未监听。
禁止占用81a1的4176/8101、Integration5180/8100或Main端口，不另开Electron/改Profile。
不分配或连接数据库，不占Migration Slot，不启动Backend/Signer/真实采集器。

使用现有受信任Node及pnpm运行时；pnpm store已存在 `C:\Users\Administrator\AppData\Local\pnpm\store\v11`。
Green的pnpm-lock/frontend package与81a1现有安装依据字节一致；优先按原锁使用现有store离线安装
本Worktree专属依赖：`pnpm install --frozen-lockfile --offline --filter @control-center/frontend...`。
离线缺包应说明具体项，必要时按原锁正常补取，不增加依赖或安装/打包Electron；
不得让共享node_modules的Vite/Vitest可写缓存影响正在运行的Integration/81a1。

## 能开始的范围与门禁

独立数据中心/商品数据页，复用当前组件/字号/主题；参照已确认的筛选、字段配置、分组和排序，
先专用Mock完成交互与测试。商品主图/标题/字符串ID最小共享复用，不重造控件或改坏候选池。
Real明确接口未接入，不请求猜测接口、不回退Mock；未知指标单位与请求契约保留未知，
源码/已有样本盘点不等于正式API契约通过。真实闭环资源后续独立确认。

Gate1交准确Candidate/范围/验证/未覆盖项后，由ca97准备匹配候选的受控前端预览。
没有用户新增视觉确认及相应Gate前不合dev/标Green或发布；本次只放行开工资源。

## 共享组件协调（既有WIP保留）

Owner已从精确Green创建该Feature并推进前端、首批定向21项通过，尚未整体Candidate/Gate。
曾见ShopSelector.clearable三行WIP，Owner接收协调后已撤回重复扩展；最终冻结由81a1原Feature单独实现透传。
7d55本页先组合现有店铺查询/选择能力，不重造基础控件；不反复恢复该WIP或另交共享片段，不让此项阻塞页面。
图片组件提取facade属于需验证的最小兼容复用，旧80/64尺寸/no-referrer/重试与候选调用必须完整保留。
本节只是协作安排，21项不代替整体前端Gate或新的人工验收。
