# Shop Login Runtime Diagnostics V1 — Gate 2 / Release Handoff

2026-10-12，Integrator ca97，Feature Owner 81a1，Main 为唯一生产发布执行者。
用户授权最小运行时诊断、登录打开反馈、真实流程复验及按 Gate 发布；不扩大选品、达人或罗盘面板范围。
本次 Integration 实际点击成功，旧生产“登录无反应”的根因仍为 UNKNOWN，不能写成生产已修复或 DEPLOYED。

## 版本、边界与合并

- Green 基线：`1718abe117c90842c8d39859a074fa988360f070`。
- Candidate：`046fd03e7124a829cb2659ba75b6c12fe0a8681d`；远端 `feat/shop-login-runtime-diagnostics-v1` 一致。
- Gate 2A：ACCEPT；Gate 1 与具体安全契约见同目录 `shop-login-runtime-diagnostics-v1-gate1-20261012.md`。
- 正常 `--no-ff` Merge：`ddd523d08ae7896498f2950123c5bdf044568a50`；合并后 Backend/Frontend/Electron 与候选字节一致。
- Backend、Signer、依赖锁、部署配置及 Migration 差异为 0；Integration 单一 `20261010_0043`，本轮未运行迁移。
- 保留旧选品 `1279cc9…`、原店铺/团队、历史任务、Profile 和旧安装器；该候选未混入本次发布。
- 最终 Green 必须取本记录收尾后精确推送提交及成功 CI，不能沿用基线或 Feature 的 CI。

## 实际 Integration 原生点击

唯一开发 Electron，Real `5180 → 8100 → control_center_integration`，Vite strictPort。
已核对实际 EXE、候选源码/编译入口、5180 正式 JS 登录 hook、Real `/` 代理和数据库身份。
复用 `g2_sa_v1_super` 已有正常人员会话；账号启用且为超级账号，没有改密码/权限、注入 Token 或另开实例。
旧生产客户端已正常退出，未强杀。原始生产 1.0.4 未被安装替换或修改。

原生 capture 两次超时，自动点击报 `coordinate input geometry is unavailable`。
这些是工具限制，不是登录根因。用户在 ca97 已筛选的唯一 HuanYu 行代点一次；不以自动点击失败算成功。

Integration HuanYu：内部 Shop `c448f225-b141-409b-bc94-12f1ae74ee04`，平台身份 `243321624`。
一次关联 ID：`66ef0056-8c3c-4194-b3cd-6eef169f41c0`。以下时间均为 Asia/Shanghai。

| 本次实际阶段 | 证据 |
| --- | --- |
| 18:41:25.000，Renderer login 入口 | bridgeAvailable / superAccount / teamSelected / platformSupported 均 true |
| focusShop IPC → Main → Session 元数据 | 实际 request 事件 18:41:25.005；HTTP 200，耗时 186 ms；focused=false 表示此前无目标留窗，不是失败 |
| 租约 | Renderer lease finish，1186 ms；之后进入 open IPC，而非停在前置请求 |
| 开窗及加载 | Main open/load 与 open IPC 完成；Renderer open 耗时 3380 ms |
| 身份与捕获 | detect finish、capture finish；后续服务端认可目标身份并成功保存，不以页面标题代替身份校验 |
| 自动保存及权威验证 | refresh finish 18:41:32.588；数据库 VALID v3 → VALID v4；captured 18:41:30.580、validated 18:41:31.645825 |
| 留窗与权限释放 | 只读核对无有效 refresh lease；原生 accessibility 的 owned 窗口仍有 HuanYu 罗盘浏览页面；主列表“有效”且登录可用 |
| 不触发经营任务 | 操作前后均为 10 Job、154 Item、0 active；没有新增经营采集任务 |

本次完整链没有错误或持续等待，不能为“找到停点”而伪造失败。
罗盘页面的局部“加载失败”仍可见，但该面板可用性已由用户明确排除发布门槛，本轮不改它。
保存后的服务端权威验证及有效状态已取得；正式 StoredSession → Accessor → Connector 的真实读取
既有证据可复用，未为证明未变代码再次请求榜单或经营数据。

保留旧候选真实留窗/重复点击只置前/关闭重开证据；新超时、迟到、取消、错误身份、撤权和首次添加兼容
另以定向合成测试记录，不将其改写为本次用户操作。正式安装器及生产实际点击仍须 Main 发布后复核。

## 运行资源与保护

启动时丢失的已登记 35433 隧道按原受信任配置恢复，StrictHostKeyChecking=yes，仅原本地 forward。
DB 读事务确认 `control_center_integration` / `control_center_dev_user` / 单一0043；未改 HBA、数据库结构或生产配置。
8100 与本地 Signer 8787 复用；采集/每日/选品执行保持 Integration 原关闭状态，本轮不使用生产密钥。

开发 SDK 默认 CookieEncryption 与正式包不同，故未用它降级读取原 Profile。
从已校验官方 Electron44.3.0 ZIP建立 ignored 完整副本，只将 CookieEncryption 与既有正式包一致，其他8项
开发 Fuse 原值不变；EXE 恰好1 byte变化。源 ZIP SHA-256
`26bf9a617d58d81772b3d68305d59ee48272969c15083c06db634a77358a8d9d`，
预览 EXE SHA-256 `78a8aef22989a18c97658d1892af3a8dd8066fdb2cf07dbe7e467bdfe72da494`。
81a1独立流式复核73个归档文件及全部 Fuse，原 SDK 与安装 EXE 均未改。
这不是原字节官方 EXE 或正式安装器；Source、AppID、userData、正常 Main/Preload、5180/8100边界保留。

工具自动启动曾被策略拒绝，未换工具代启。用户执行正常本地入口后，因旧 PowerShell936解码Git UTF-8
中文路径触发原路径 guard；仅 ignored facade 设UTF-8并在finally恢复编码。原 collector blob、路径校验不变，
只读实测936下正确路径通过、越出`.codex`仍拒绝；随后用户正常启动并完成上述真实操作。

## 合并后验证

Node 使用既有24.19.0。只补本次相关验证，不重跑未改 Backend/PG 或既有全量审计。

| 检查 | ca97 合并后结果 |
| --- | --- |
| Frontend lint / typecheck | PASS |
| 登录 hook 与真实列表按钮 unit | 2文件21 PASS：19 hook、2列表按钮 |
| Real production build | PASS；原有500kB chunk提示保留，不做无关重构 |
| Electron typecheck / compilation / unit | 43 PASS，0 fail；原生、超时和日志安全合成覆盖分开 |
| Real浏览器拦截契约 | 合并后3 PASS；1366×768，复用5180、全部API/desktop能力拦截，无新服务/DB/平台请求；不是原生证据 |
| Git diff/check、敏感文件与凭据计数 | PASS，敏感tracked文件0、凭据literal匹配0；本机材料ignored |

Owner627 Frontend、43 Electron、3 Real浏览器合成测试和正式打包证据复用；不与 ca97 数量相加。
Gate 2B 的真实最小流程 PASS；Green、Release 和生产收口各自有独立门槛。

## Main 交付及生产核验

匹配Source Candidate的1.0.5正式NSIS：
`D:\中控台\dist\desktop\1.0.5-046fd03e7124\Siyu-AI-Control-Center-1.0.5-046fd03e7124-windows-x64-setup.exe`。
120308277 bytes；ca97独立SHA-256
`0bf823cd633f33fdec800458a02b257553f08e9296c891bfc1fac6d2c57b7fd3` 与 manifest/checksum一致。
NotSigned、固定AppID/userData、生产Origin及正式安全Fuse不变；保留已校验1.0.4回滚安装器。

Main先核对其本地规则/未提交工作、当前生产e0版本、0043、备份及恢复路径；精确Green CI通过前不推main。
Release仅本候选范围；main精确CI及正式Deploy与服务器健康单独记录，不以服务器更新代替客户端升级。
匹配1.0.5实际客户端使用保留Profile，经正常人员认证后跟踪一次生产目标店铺登录。
记录同次bridge/team/IPC/GET/lease/open及Session版本/验证时间：失败则以首个真实停点退81a1最小返修，
成功才记录本次生产流程无复现并核验保存后可用；旧故障原因无法还原时仍如实UNKNOWN。
不让用户重做未改的整页视觉，不要求罗盘面板正常，不把Integration v4搬到生产。
生产店铺Session更新及实际客户端核验未完成前不标记DEPLOYED，不扩大历史补采或每日配置范围。
