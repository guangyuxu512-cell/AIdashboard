# 店铺身份来源与错店纠正 Gate 2

## 当前结论

精确 Candidate `998f3fdfa24249d333ced90d636536604f702ad4` 的 Gate 2 合前评审和集成验收通过，
ca97 接受该候选。独立技术验证及匹配 Real Electron 的正常保存、错店保旧留窗、同窗口显式纠正
均已完成，没有待修业务缺陷，也不重复这三轮登录。

正式交付Candidate为`d65ed079e4bcc451ef144059c54d52e78f1815bb`（P），直接父998；
仅package版本和两份原交付记录，业务Runtime、Frontend、Backend及构建脚本与998全部blob相同。
P与匹配1.0.8包独立审查通过，接受合入；Owner已完成正式Handoff，Source远端一致且工作区干净。

Gate 2 流程尚待正常 no-ff 合入 dev、合后复验及精确 CI，当前不是新 Green 或生产交付。
人类在规划turn `01a146fd-f4c5-7383-af58-d41e0b5c9f3b`对完整范围明确“同意”，已授权最小1.0.8交付候选/
匹配包、正常dev合并及精确CI、Main Release/main CI/三服务部署和部署健康后的覆盖安装。
生产MyCookLab最多1次正常Login/refresh，须临近点击新鲜安全前检后由用户操作，失败即停。
这不是沿用旧诊断权限；当前尚未部署或安装，生产验证未执行，不以集成结果替代。

Owner81a1 使用 `feat/shop-login-identity-source-v1`，基线为已通过精确 CI 38941889261 的
Green `e4b70a272b0327efb5d5aa0768811d6315dd123d`。现有生产保持
`c085a3f75a84f9ac68ea9da7473782431de252a3`、单一 `20261015_0046`；本次审查不改变生产。

## 范围和资源

实际范围为核准的10个运行路径、8个定向测试、3份现有契约及Gate 1记录，共22路径。
远端分支与998精确一致，归档22份blob零差异；Backend、Shared、选品、Main窗口入口、IPC handler、
运行配置、Worker、部署脚本、package及lock不变。两个Vue文件的style逐字不变。

不分配新数据库、端口、服务或Migration Slot，不借旧登录Feature库；0046保持。
独立技术阶段仅在ignored源码快照中链接已有依赖，未安装依赖或访问现有Profile。
获准的原生阶段沿既有受信任35433隧道恢复匹配8100/5180服务和唯一开发Electron，复用原Profile、
人员会话及店铺映射；未重绑、清Cookie、导入生产Session或创建第二实例。
功能候选998的开发package为1.0.6，P正式交付package为1.0.8；本轮Adapter、Main Service及Preload
必须成套加载匹配代码。当前开发实例运行字节与P相同，正式1.0.8安装仍待生产发布健康后进行。
旧a488的1.0.7包不是本候选，不得借旧包或仅服务器前端部署声称本次客户端已更新。

## 已审查的行为

抖店仅从已验证的SHOP_INFO_V2读取明确的`data.shop_id/shop_name`，要求HTTP成功、兼容业务st及
data对象。账户字段、递归同名字段、数组首项、未知类型和不安全数字不组成店铺身份；四条未确认
ShopID契约的fallback取身份调用撤下，没有新增端点或平台重试。原Backend权威身份检查不变。

只有`candidate_identity`或明确`PLATFORM_IDENTITY_MISMATCH`归为错店。候选被拒后清零payload、
释放旧租约并保留浏览窗口和原Session；人员认证、权限、平台认证、Schema、网络和未知错误独立处理。
用户通过原“登录”显式继续时重新取得当前权限下的新lease和expected version。相同被拒候选不重复POST，
同一attempt最多三次显式POST；失败观察只读状态，不自动捕获、提交、切换绑定或清空Profile。

列表原96px状态格仅对本次错店显示既有小型状态标签和Tooltip，详情复用NAlert。
元数据加载或读取失败时，本次错店提示与原Loading/ErrorState及重试并存；不把旧查询当新结果。
提示只使用当前授权目标店铺，不覆盖数据库VALID状态。取消、自然关闭、成功或人员/团队/权限变化
清除本次反馈，不持久化或重播历史提示。首次新增仍识别后自动关闭，其他已确认布局不改。

## 退回和修复

首候选`bc4bdc80c6bb28d7a358233ec34ad7904042b00b`的独立83项Electron、61项Frontend及构建通过，
但ca97追加的实际Service合成检查发现：已有店铺恢复在identified阶段，通过状态IPC返回了尚未经过
目标验证的捕获身份，直到刷新拒绝后才清除。界面不显示这些值不能代替桥接数据隔离。
该结果是合成复现，不是生产泄漏证据；ca97退回Owner，没有在dev代修。

998直接父为bc4，返修仅4路径，唯一运行改动使用永久`recoveryShopId`使恢复全流程的状态identity为null，
包括lease已释放及显式继续阶段。Main内部身份和payload仍用于验证与保存，首次新增身份展示保持。
同一独立检查在998通过，并保留bc4失败结果作为负对照。

## 独立验证

| 验证对象 | ca97结果 |
| --- | --- |
| 精确父链、远端、22路径及归档 | 通过；未授权路径0，blob差异0，diff check通过 |
| 998的TypeScript编译及全部Electron Node测试 | 83通过，无失败、跳过或取消 |
| 实际Service身份边界检查 | 恢复identity不外传；内部身份/payload保留；拒绝分类、首次新增身份正对照通过 |
| Frontend四文件 | bc4独立61通过；998完整Frontend tree与bc4均为`d87cc72ccb5cad1aabb3d2aabbf9726c3ef873a3`，按字节复用 |
| Frontend完整lint、typecheck及Real build | 通过；build16.93秒，仅既有大chunk警告；998复用相同Frontend tree |
| 运行隔离 | 真实网络及现有Profile访问拒绝哨兵均0；DB、平台、原生窗口、服务及安装操作0 |

以上为源码与合成执行证据；对应真实登录及原生留窗结果见下一节，不混记来源。
本机脱敏归档和结果位于ignored的`.codex/review-shop-login-identity-bc4bdc80-utf8/`及
`.codex/review-shop-login-identity-998f3fdf-utf8/`；不提交日志、PID、截图或凭据。

## 真实 Integration 三轮结果

实际环境为 Real `5180 → 8100 → control_center_integration`，单一 `20261015_0046`。
Renderer来自998精确快照，Main/Preload/Service编译散列与启动记录一致；不是旧a488壳配新Renderer。
用户在现有 `g2_sa_v1_super` 会话中亲自操作，入口诊断为super=true、teamSelected=false。
登录只针对既有HuanYu，UUID为`c448f225-b141-409b-bc94-12f1ae74ee04`，平台ID为`243321624`。
时间均为2026-10-17 Asia/Shanghai。

| 轮次 | 正式提交及验证 | 数据库结果 | 原生结果 |
| --- | --- | --- | --- |
| 06:23前置正常保存 | refresh 1次HTTP200；Adapter身份probe 1次HTTP200；Backend权威身份读取1次 | valid v7→v8；captured 06:23:28.527，validated 06:23:29.903366；租约清除 | 保存后留窗，捕获结束；用户随后正常切另店并在06:36:12.973关闭该浏览窗 |
| 06:40错店登录 | refresh 1次HTTP500；固定码`REFRESH_CANDIDATE_IDENTITY`，分类identity_mismatch；Adapter身份probe 1次HTTP200，Backend权威联网验证0次 | 原valid v8、密文单向摘要、采集/验证时间及绑定均不变；DELETE204释放租约 | 仅显示目标HuanYu的错店说明，平台窗口保留，原登录入口可显式继续；不自动再捕获或保存 |
| 06:53原窗显式纠正 | 同attempt获取新lease后rearm原窗口；唯一refresh HTTP200；Adapter身份probe 1次HTTP200，Backend权威身份读取1次 | valid v8→v9；captured 06:53:17.328，validated 06:53:18.622478；正确目标且租约清除 | 同一浏览窗继续保留，错店说明和忙态清除，普通“登录”恢复 |

前置CID为`57060c50-ec48-4454-b86d-703d6ee2bd40`；错店和纠正共用
`1149f08a-5e91-4a0f-a6e2-6ad42c989478`。后者06:53:17.184取得新租约，原窗rearm IPC于
17.189完成，refresh于19.839完成，未新建窗口或延长原超时。人员、团队及目标上下文没有切换。

合计refresh **3次**，HTTP依次200/500/200；lease取得3次，失败释放DELETE 1次，两次成功原子清租约。
Adapter官方身份probe共3次，Backend权威身份读取共2次；这不是平台自然页面与人工认证的全部网络计数。
三次授权预算已用完，ca97没有代点、额外验证会话、平台探测或重试。

原生证据来自同一主窗口的完整AX树：罗盘浏览窗是owned子窗口，虽未单独列在窗口清单，
树内实际存在平台窗口及WebArea。用户只确认操作及错店提示；留窗、最终状态和反馈清除由ca97独立核对，
不伪记为用户整体人工确认或原生截图。平台自身脚本错误只保留固定枚举，不扩为经营面板验收门槛。

原10表任务与事实逐行摘要全部保留，仍19经营Job、2820 Item、667日事实；HuanYu为26成功、128历史失败，
pending/running/paused均0，选品活动Run为0，另一未配置Session元数据不变。
Integration背景执行和计划开关保持关闭，没有为绕过待恢复项检查而更改配置。错店前已建立v8密文摘要，
拒绝后精确相同；未导出Cookie或payload。首次v8保存时没有单独留密文摘要，不补写更早的字节对照。

人类关键回复依次为`01a146d0-4edf-77f3-b691-90208e6a0a49`（前置已点击）、
`01a146dc-0ea1-7a82-9418-589722dbdc8c`（切另店并关闭）、
`01a146e0-bf13-7e41-9dbe-2f6ef3e36da6`（店铺不符）、
`01a146e5-0af9-72b0-b1d4-cb2fae86d9f1`（切回并留窗）、
`01a146eb-a5c0-74d3-8dff-ce38164b6b06`（最终显式继续）。
脱敏日志、数据库摘要及三轮结果保存在上述ignored审查目录，不提交本机材料。

普通成员、首次新增、PDD及其他失败分类沿用本次83/61定向验证和未变路径证据，
不额外要求真实账号或重复整体视觉。新的正式包安装、生产MyCookLab验证仍属于后续交付，不倒写为通过。

## 生产事实和正式交付

已部署c085只增加Backend安全诊断。2026-10-17北京时间02:37:40的一次MyCookLab刷新返回
HTTP500、`SHOP_SESSION_PAYLOAD_INVALID/candidate_identity`，候选ID与目标ID不等；尚未进入Backend
权威联网验证、保存或采集恢复。原valid v1及加密payload保留，客户端旧失败清理主动关窗。
这不能证明本次实际取自account字段，也不能认定用户登录错店；同次身份源字段没有留存。

该次生产点击预算已使用，不能用诊断授权继续登录、验证、平台请求或改业务数据。
旧正式客户端、Profile、Integration数据及已通过的选品A/B结果保持；本轮列宽诊断不混入。

998相对生产c085的功能净差仅本次10个Electron/Frontend运行路径，Backend树逐字相同，
现有安全诊断保留；Shared、选品、Signer/Worker、依赖及Migration均不变。
完整树对比另显示Main独有的AGENTS原则1行及桌面Gate规则10行，来自Main相对共同基线e4b的治理追加；
正常三方合并应保留，不能把998整树覆盖生产而删除这些规则，也不带入cleanup或商品数据。

旧`1.0.7-48dd`及`1.0.7-a488`安装包完整保留，不用于998交付。下一版建议1.0.8；Owner与Main在现有
工作树、登记和交付目录未发现占用，Owner远端版本/Release及历史核对也未发现1.0.8。
1.0.8按上述直接人类授权正式reserved给Owner81a1；1.0.7旧候选和包封存保留，不再用于此次交付。
Owner已从干净P执行原`package:win`，83 Node通过，x64 NSIS、PE和9项Fuse通过。
ca97独立复核EXE/checksum/manifest、应用EXE与ASAR散列；ASAR的16个运行JS逐字匹配已审核998编译文件，
归档共17文件、白名单外文件0。Source自动为P，版本1.0.8/应用ProductVersion 1.0.8.0，
固定AppID、生产Origin、userData、Cookie encryption与unsigned契约保持。未运行安装器或打包应用。

交付目录为`D:\中控台\dist\desktop\1.0.8-d65ed079e4bc\`，安装器为
`Siyu-AI-Control-Center-1.0.8-d65ed079e4bc-windows-x64-setup.exe`，大小120311761字节，SHA256为
`06efddb7e50feeb59cfb502e31a23f57cc294c0b5e33aa3982be6b413b898a87`。
ASAR SHA256为`c6effd27e480c1f18ae9985a8ca4f36bc2ff838dc578db2add49568159047574`；
匹配的manifest、SHA256SUMS及Owner验证记录同目录保留，ca97独立结果在ignored交付审查目录。
纯版本增量复用已验三轮和完全相同Frontend tree，不重复登录。

后续完整范围为：Owner最小交付候选与匹配包→ca97增量审查及正常no-ff合dev→合后定向和原生只读复验→
精确dev CI→Main Release Gate、正常合main/main CI和正式部署→用户正常退出开发实例、同AppID覆盖升级新包→
确认实际安装版本/Source与生产Origin→指定MyCookLab一次受控登录验证。
合后只读列表/详情和现有留窗复验不追加平台请求；本次三轮不重跑。

最小交付源码变更只涉及`electron/package.json`的版本、原发行文档和原Gate1交付记录；
root package、pnpm-lock、构建器及构建脚本不变。安装器的Source为上述实际P，不是后续dev或main合并SHA。
既有NSIS为unsigned、人工覆盖升级，runAfterFinish会启动正式客户端。

服务器功能更新是Frontend；既有正式流水线仍构建并up全部Backend、Frontend、Signer到同一精确Release，
不因后两者业务源码未变而沿用旧镜像SHA或临时旁路只换某个容器。
本轮无新Migration，0046及既有执行、定时和密钥配置保持。安装使用固定AppID/userData与发行Fuse，
保留人员Cookie、平台Profile及映射，不卸载或重置。服务器和客户端就绪前不要求用户安装或生产点击。

生产MyCookLab验证前须新鲜核对实际Release、账号权限、目标绑定、旧Session/租约和全部可能被原恢复路径
触及的待处理项；存在活动任务或未明确副作用就停，不修改开关规避。拟只允许一次正常登录/refresh及
其内置权威身份验证，读取安全日志/元数据确认正确目标、新版本、租约和留窗；失败不自动重试或扩店补采。
该生产预算已获上述新授权，但在部署、匹配正式客户端和临近点击的安全前检完成前不可使用。
本次没有新生产请求；匹配新包和生产核验完成后，才能宣告正式交付收口。
