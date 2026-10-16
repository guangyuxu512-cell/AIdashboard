# 商品数据支付时间退款率修正 Gate 1 交接

2026-10-16，Owner 7d55，交接 ca97。沿原 `feat/shop-product-data-frontend-v1` 在已推送的
`a28f8d3ac10c6c79ce05598db5f02071b877317b` 上做定向口径修正，保留 b9/a28 及所有旧报告。
基线仍为原候选已包含的 Green `5a18bd0390cb4b8cbed637d412f7482cefff3f36`。
新完整候选为包含本记录的 Feature HEAD，精确 SHA 与提交后 Real 构建结果见回执及本地忽略清单。
仍为 UI_ONLY；待独立 Gate 2 和用户验收，禁止发布。

## 用户修正与实现

已回读规划人类 turn `01a1449d-2ad6-7ce0-8145-2e1ecb0a3a61`：
“退款率用这个，也就是发货前+发货后的”。本条替代之前的发货后退货率目标。

展示列、字段配置、详情与九项筛选统一为“退款率”，Tooltip 为“退款率（支付时间）”，
前端语义 ID 为 `payTimeRefundRate`；目标 code 为 `pay_refund_ratio`。
使用平台总体退款率，不相加发货前后百分比，不以 `sold_pay_refund_ratio` 或退款时间指标替代，
也不在前端根据订单数手工重算。17 个独立目标指标、19 个中文名称及两组别名保持不变。
区间仍为不限、自定义和 0–10%、10–20%、20–30%、30–50%、50%以上，继续含下限、不含上限。

旧 `shippedReturnRate` 只在列偏好读取时迁移显示位置/可见性并去重，原存储不自动回写；
它不再是指标别名，旧数据和筛选不迁移。Mock 保留独立合成值，不导入 Integration 数据或计算两阶段比率。
长口径说明经截图发现超视口，四处现有 NTooltip 复用 Feature 内的 Token/视口最大宽度与换行参数，
没有改 Shared、主题或新增通用 Tooltip/筛选框架。默认 20 条、布局和日期规则不变。

## 既有响应离线核对

只读核对 ca97 的 `product-list-date-back-one-20261016/result.json`，没有连接数据库或请求平台。
该投影来自先前成功的 70 指标响应，不是新的 74 指标返回。
文件 SHA-256 为 `F31B48B37ED10B937C6979F9727C49FCCED16FD10CB1C64CF4BC86799BBD9AD9`。

`pay_refund_ratio` 的 meta 是“退款率(支付时间)”，tip 为“退款订单数(支付时间)/成交订单数”。
10 行均为 unit4：3 个正值、7 个显式 0，首行原始 decimal 为 `0.10384608086826178`。
只确认名称和实际返回形态，保留平台原值；该 tip 不授权自行重算或推断未冻结的单位缩放。
本模块的 Real mapper/API 仍未接入，其余次数/比率的真实返回与单位缺口继续保留。

## 定向回归与停止点

新候选复跑商品数据 7 文件 67 项单测、lint/typecheck，全部通过；原 compact/main 流程及新增退款率
浏览器用例共 18 项通过，0 fail/skip/flaky。
新用例覆盖筛选总量、字段显示、旧名称消失、官方口径可见/不超视口及详情；其余回归继续验证
九区间边界、缺失值、偏好兼容、四主题/三视口、默认 20 条、分组与错误恢复。
最终报告保存在忽略的 `frontend/test-results/product-data-refund-rate-v1-unit-final/` 和
`frontend/test-results/product-data-refund-rate-v1-browser-final/`，实际结果按回执记录，不合并累计原 a28 的 65/17。
首次浏览器 17 通过/1 失败报告保留于 `product-data-refund-rate-v1-browser/`：
测试误假定既有 Naive Tooltip 带 tooltip 角色；实看截图同时修正长说明超视口，再复跑验证。

继续使用已有 4177 Mock 预览及原进程，本轮未启动/重启服务、恢复隧道、打开 Electron 或操作 Profile。
无平台/Signer请求、DB连接/写入、Schema/Migration/Worker/生产改动；Migration Slot 与 Feature DB 仍为无。
ca97 根据新完整候选做 Gate 2；本候选新 Real 浏览器、原生 Electron 与人工确认均未覆盖，不合 dev/main 或发布。
