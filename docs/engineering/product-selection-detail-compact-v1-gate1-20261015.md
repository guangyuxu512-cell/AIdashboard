# 候选详情局部紧凑返修 Gate 1（2026-10-15）

## 范围与基线

Owner81a1沿`feat/product-selection-candidate-result-filters-v1`接续精确父候选
`cbe30cb3a941116292b71fae4e164fd9ccc249e6`。候选池38e9abf视觉确认及cbe默认20保留，
纯共享Radio141fec65独立封存、未合入此业务分支。本轮只详情字号/间距/底栏当前能力反馈与
必要定向测试；不改Shared、全局Drawer/主题、候选池源码、后端、API/数据库契约、0046或执行配置。

## 实际旧值与新值

| 项目 | 旧详情 | 本轮局部值 |
| --- | --- | --- |
| 商品标题 | 18px / 600 | 16px / 600，原section-title Token |
| 分区标题 | 16px / 600 | 14px / 600，原body Token |
| 普通字段值 | 14px / 400 | 13px / 400，原secondary Token |
| 字段名 | 13px / 400 | 13px / 400，次文字色保持 |
| 周期/时间/状态 | 13px及默认14px | 12px，复用已有紧凑字号Token |
| 四项视频数值 | 22px / 600 | 18px / 600，原page-title Token |
| 详情按钮 | 默认34px | 局部Button theme 28px高 / 13px |
| Descriptions padding / 分区gap | 12px / 16px | 8px / 12px |

仅本组件`NConfigProvider abstract`覆盖Button尺寸，不新增公共API或全局Provider规则。
各字段主次颜色、成功/错误语义色、区间和真实0/未知规则保留；摘要图仍80px、现有图片预览与复制不变。
两列有边框视频/排名区、全部基础字段、默认折叠来源区及两个独立时间保持。

底栏由状态区和右侧不换行按钮组组成，gap12px；560px默认抽屉两区分开，420px窄抽屉状态
自然独立一行。已保存成功显示“上次基础信息已更新”，当前capability关闭独立显示
“当前环境暂停更新”，两者不互斥。运行中/排队/部分/失败/中断和查询错误保持原映射；
实时完成toast原文不变。“采集资料”Real继续禁用，现有Tooltip说明“资料采集待接入”。
没有启用执行、平台请求、数据库写入或恢复Fake成功。

## 验证与证据边界

所有命令在本Feature的`frontend`运行；只使用4176 strictPort，未启动Backend/第二Electron。

| 命令 | 实际结果 |
| --- | --- |
| `pnpm lint` | PASS（完整前端lint） |
| `pnpm typecheck` | PASS |
| `pnpm exec vitest run src/features/product-selection/ui/CandidateDetailDrawer.spec.ts src/features/product-selection/model/basic-display.spec.ts --maxWorkers=2` | 2文件11项PASS，最终6.81s；成功Run/仅字段状态、pending/running/partial/failed/interrupted与当前关闭并存、禁用零提交，以及原区间/未知时间/0和商家身份 |
| `pnpm build` | Real生产构建PASS，Vite16.79s；既有大chunk告警保留 |
| `pnpm exec playwright test --config playwright.selection-real.config.ts e2e/production/product-selection-detail-compact.spec.ts --workers=1 --output ../.codex/selection-detail-compact-v3-20261015 --reporter=line` | 四主题4项PASS，49.0s；1366×768/1920×1080及测试限定420px抽屉，实际计算字号/颜色/28px按钮/间距/无横溢、原始区间/零/缺失、19位ID剪贴板、图片预览/折叠来源/两个时间、历史成功与当前暂停；所有API及图片完全拦截，写请求0/外部请求0/Mock模块0/pageerror0 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-selection.spec.ts --grep 'detail typography:\|detail missing timestamp' --workers=1 --output ../.codex/selection-detail-legacy-20261015 --reporter=line` | 2项PASS，21.2s；四主题原详情字号/主次颜色/窄宽、原始区间、长标题/缺失时间/真实0及两个时间来源。只跑受影响详情用例，不跑列表历史全套 |
| `git diff --check` | PASS |

第一次typecheck发现新增测试DOM wrapper回调推断any，已改用原Vue wrapper的组件查找并通过。
首次浏览器脚本用Escape关闭预览同时关闭原Drawer而超时；改为点击图片既有遮罩关闭，未改图片组件
或键盘处理。测试还补齐原只读latest Run的HTTP拦截；首轮截图/超时记录保留在独立ignored目录，
不称其最终通过。v2四主题4项已通过26.9s；v3补主次颜色断言并等复制toast消失后截图，未改运行源码。

最终实际截图/计算值在ignored`.codex/selection-detail-compact-v3-20261015/`，每主题：
`{theme}-1366-detail.png`、`{theme}-1920-detail.png`、`{theme}-detail-narrow420.png`及两个JSON。
均是**Real Renderer＋完全拦截HTTP合成数据**，不是平台、DB或Electron证据。
已人工查看四主题及窄抽屉截图；旧用户反馈只有底栏截图，不伪造同数据全页“之前”截图。

## 交接与恢复

提交推送精确Candidate后交ca97，更新原5180/唯一Real Electron，保留Profile/登录/Integration0046数据。
只补本轮详情普通/宽屏/窄宽效果和禁用原因确认，不重复已确认列表视觉。是否实际加载、原生操作及
用户详情确认由ca97提供，本Gate 1不能替代。

ca97后续回传（独立Integration证据，本Owner不重复请求）：经规划人类明确同意后，正式Run
`59394f85-2df5-4e2e-9882-223ee9dab4ba`已通过原production工厂单次执行，Signer1/basic GET1、
HTTP200/整数st0、succeeded/saved0/supplemented1，三字段available；其DB/正式API一致。
该真实单项不再登记为“尚未执行”；本轮图片仍是合成前端证据，不拿它冒充该真实数据。
ca97已恢复执行/定时false、lifespan off及原guard；用户原生Escape停止后只取得底栏截图，
新详情及0.03%值仍待同一Electron集中确认，不重复提交或故意制造平台失败。

无新Migration/DB/桌面主进程修改，无新安装包要求，无发布授权。本次应用恢复可回cbe详情组件，
不回退数据库、清理运行记录或改0046；不影响保留的已发布A/B及每日采集配置。
