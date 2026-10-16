# 店铺身份来源与错店纠正 Gate 2

## 当前结论

精确 Candidate `998f3fdfa24249d333ced90d636536604f702ad4` 的独立技术审查通过。
本候选尚未加载到真实 Electron，整体 Gate 2 仍进行中，不合入 Feature、不触发 CI 或发布。
后续原生验证、客户端版本及安装、真实请求和业务发布须由规划按精确候选取得明确授权。

Owner81a1 使用 `feat/shop-login-identity-source-v1`，基线为已通过精确 CI 38941889261 的
Green `e4b70a272b0327efb5d5aa0768811d6315dd123d`。现有生产保持
`c085a3f75a84f9ac68ea9da7473782431de252a3`、单一 `20261015_0046`；本次审查不改变生产。

## 范围和资源

实际范围为核准的10个运行路径、8个定向测试、3份现有契约及Gate 1记录，共22路径。
远端分支与998精确一致，归档22份blob零差异；Backend、Shared、选品、Main窗口入口、IPC handler、
运行配置、Worker、部署脚本、package及lock不变。两个Vue文件的style逐字不变。

不分配新数据库、端口、服务或Migration Slot，不借旧登录Feature库；0046保持。
仅在ignored源码快照中链接已有依赖，未安装依赖、启动服务或访问现有Profile。
当前package仍为1.0.6；本候选修改Adapter、Main Service及Preload，后续必须成套加载匹配代码。
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

以上均为源码与合成执行证据，不代替真实登录或原生留窗验收。
本机脱敏归档和结果位于ignored的`.codex/review-shop-login-identity-bc4bdc80-utf8/`及
`.codex/review-shop-login-identity-998f3fdf-utf8/`；不提交日志、PID、截图或凭据。

## 生产事实和后续门禁

已部署c085只增加Backend安全诊断。2026-10-17北京时间02:37:40的一次MyCookLab刷新返回
HTTP500、`SHOP_SESSION_PAYLOAD_INVALID/candidate_identity`，候选ID与目标ID不等；尚未进入Backend
权威联网验证、保存或采集恢复。原valid v1及加密payload保留，客户端旧失败清理主动关窗。
这不能证明本次实际取自account字段，也不能认定用户登录错店；同次身份源字段没有留存。

该次生产点击预算已使用，不能用诊断授权继续登录、验证、平台请求或改业务数据。
旧正式客户端、Profile、Integration数据及已通过的选品A/B结果保持；本轮列宽诊断不混入。

下一步由规划确认本候选的Integration窗口切换与有限真实验证范围，ca97再准备同一实例的匹配
Renderer/Main/Preload和明确店铺、样本。当前窗口不是998，不要求用户现在操作，也不重复未变的视觉验收。
本次只读运行检查中8100/5180仍为旧预览进程，35433没有监听；旧`.dev-runtime`记录不能证明连接可用。
获准后由ca97沿已有受信任配置恢复隧道及匹配服务，不申请新环境、不要求用户配置服务。
完整Gate 2通过后才正常no-ff合dev、等待精确Green CI；生产Release与匹配客户端交付另按授权执行。
