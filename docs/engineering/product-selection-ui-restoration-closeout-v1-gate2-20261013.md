# 选品界面恢复收口 Gate 2

2026-10-13，ca97 / Integration。

## 候选、范围与结论

- Candidate：`30e8cc63bc3c770cee65bd02c57d56e39740e255`，分支 `feat/product-selection-ui-restoration-closeout-v1`，与远端一致。
- 起点 Green：`22403a1094b25b7569427d5383e4e28154253d79`；候选包含该基线。
- 正常 `--no-ff` Merge：`3ec8b318b327bd0a212841b3b03fcf5018946509`；无冲突，不改写旧提交。
- Gate 2A、Gate 2B及合并后定向复验 PASS。精确最终dev提交、CI和Release结果按后续Handoff / Main发布记录核验；本记录不把本地通过当作CI或DEPLOYED。
- 相对起点仅AGENTS、工程登记、Gate 1文档与`SelectionWorkspace.spec.ts`变化；Frontend运行源码、Backend、Electron、Worker、Mobile、依赖和Migration无变化。
- 原389030a恢复和6e6bfc6体验成果已经在Green。本轮补防回退测试及原生尺寸证据，不重复改界面或取数规则。
- 98d48d4登录候选不是本轮候选祖先；关闭后仍“登录中”的独立失败证据保留，本轮不修复、不合入该返修。

## 实际环境及加载核验

- ca97 `dev` 工作树清洁后评审；启动前确认旧开发Electron确已退出，未归因于生产客户端。
- 仅正常本地启动入口重开一个开发实例，固定既有userData/Profile，保留人员会话与店铺Session；不强杀、不开第二实例。
- Renderer来自精确Git archive候选快照，Vite `127.0.0.1:5180 --strictPort`；实际父启动脚本和新增测试源标记均匹配候选，不只看分支HEAD。
- Real显式同源配置：`VITE_API_MODE=real`、`VITE_API_BASE_URL=/`、`/api`代理到`http://127.0.0.1:8100`。
- 复用8100 Backend，`/health`为200；只读预检真实数据库`control_center_integration`、应用角色`control_center_dev_user`、单一Head `20261010_0043`。
- 集成人员`g2_sa_v1_super`启用且为超级账号；用户截图显示相应登录会话。没有重置密码或注入认证。
- 观察用Main/Preload仍为98d48d4预览壳1.0.6，Renderer为上述选品候选；不冒称桌面壳来自30e8cc6或已经发布1.0.6。新选品候选Electron代码无差异，无需新安装包。
- HuanYu仍为valid v6，无有效刷新租约；经营Job 10、Item 154、活动Item 0保持。未执行Migration或本轮榜单/经营采集。

## 真实Electron人工证据

用户针对本轮普通/最大化、四级类目与三级“全部”专项清单反馈“目前看是没问题”，并提供两张真实Electron截图。

- 普通窗口：原策略抽屉、请求店铺HuanYu、策略名称、纵向短视频/百应、近7天、定时草稿及底部操作保留；已选四级路径完整显示。
- 最大化：四列类目菜单完整展开，有三级及四级“全部”、滚动条、实际选中第四级条目；未见抽屉遮挡或视口裁切。
- 已选路径为“智能家居 / 居家日用 / 居家布艺 / 十字绣及工具配件”。用户确认归档为本轮原生界面验收通过，不再重复整体视觉确认。
- 截图本身不证明后台请求数或父级提交参数；真实父级归一化、禁止伪造ID、权限和不隐式提交仍以本候选service/unit及已完成的完全拦截E2E证据为准。本轮没有为了尺寸额外提交真实榜单。
- 手动获取在该Integration配置中未启用，截图中的相关提示及禁用按钮如实保留；不将此布局验收冒充新的平台取数成功。

两张原图仅在本机被忽略目录保存，未上传Git：

| 本地证据 | SHA-256 |
| --- | --- |
| `.codex/gate2-selection-closeout-v1/native-evidence-20261013/user-native-normal-drawer.png` | `2fb944b3ffa67273878fa177c61623955fc9c48310dd7488bf1c4f38a382c164` |
| `.codex/gate2-selection-closeout-v1/native-evidence-20261013/user-native-maximized-four-level-menu.png` | `68c769d96c949a2435a1790aa9989dc66013b752caecdba2be9f1807a0be0c94` |

自动原生捕获返回`FrameArrived timed out`，重新选择窗口后仍`window capture timed out`。使用用户实际操作/截图，没有用网页或Mock截图替代原生证据，也不把捕获工具故障当成业务故障。

## 技术审查与合并复验

Owner精确候选的lint、typecheck、12文件86项、Real build、3项完全拦截E2E证据经审查复用。后者是浏览器契约测试，不是平台或Electron证据。
ca97在合并后的实际代码独立执行：

| 验证 | 结果 |
| --- | --- |
| `node node_modules/vitest/vitest.mjs run src/features/product-selection` | 12文件、86项PASS，18.44秒；含Workspace 12项、父级全部、原抽屉、错误反馈、缓存与权限上下文 |
| `node node_modules/eslint/bin/eslint.js src/features/product-selection/ui/SelectionWorkspace.spec.ts --max-warnings 0` | PASS |
| `node node_modules/vue-tsc/bin/vue-tsc.js --noEmit -p tsconfig.app.json` | PASS |
| `VITE_API_MODE=real node node_modules/vite/bin/vite.js build --mode production` | PASS，25.78秒；既有大chunk告警保留 |
| 合并代码与候选的Frontend/Backend/Electron/Worker/Mobile比较 | 完全一致 |
| `git diff --check`、本地材料忽略及只读运行核验 | PASS |

没有重跑无关Backend/PG全量回归或重新申请数据库。0042/0043字节保持，无新Migration Slot。
后台运行记录和商品详情日期、现有Session/Signer、有限日期回退、持久化及Team/Shop权限均保留。

## CI、Release与回滚边界

Gate 2工程记录收尾后只推精确dev提交，等同SHA的完整CI成功才能交Main Release Gate；Main不得混入98d48d4关闭缺陷或其他功能。
本轮对已发布运行代码没有增量；Main应对照main到Green的完整差异决定登记收口及是否存在实际部署需要，不为新测试SHA声称新增业务能力已经上线。
策略保存、定时、达人、百应及手机未接入部分维持原边界，不以本轮验收宣布完成。
旧分支、候选、包、Profile、数据库及故障证据全部保留。若必须回滚，只正常revert本轮测试/登记提交，不清库、不改写0042/0043、不回退已确认真实取数底座。
