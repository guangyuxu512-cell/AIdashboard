# 商品数据前端 V1：资源放行（非业务/发布通过）

Owner 7d55，Integration ca97；规划聊天直接人类确认前端方向并要求正式分配，Main仅负责未来合格Release部署。
本阶段仅独立商品数据前端及源码/契约只读盘点，不与81a1候选池修复合并，不接真实后台/平台/调度/通知。

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
