# AI图片完整等比显示热修 Gate 1

## 范围与资源

- Owner分支：`hotfix/ai-image-aspect-ratio-v1`；基于精确Green `59894d98d88eff3529fb9d6b4cfecd45694d2156`（CI39138982653四项成功）。最终精确Candidate由本记录所在提交的交接回报给出。
- 工作树：`C:\Users\Administrator\.codex\worktrees\local-ssh-production-deploy\中控台`。无数据库、Schema、Migration Slot、端口、Backend、Electron或生产连接；旧SSH/缓存分支、Profile与集成环境保留。
- 仅实体图片/AI消费者显示、既有单元与Real浏览器回归、文档及原 `frontend-real-build` 的一个定向步骤。四个CI Job及原门槛不变；按锁定版本安装Chromium，不加依赖。
- 不改ProductImage/候选池、API/DTO、依赖/锁文件、生成尺寸/模型/Provider、上传/生成/归档业务或数据库。

## 已复现的原因和最小修复

1. 原选择器/即时输入结果等局部 `cover` 经共享图片 `inherit` 生效，非方图裁切。原样式的Production Bundle在真实Chromium横图测试收到 `cover`，期望 `contain`，稳定失败（861ms）。共享真实img改为统一 `contain`，删除各处局部cover/无效或重复img覆盖；卡片槽保持规整。
2. 仅改contain仍不能保证完整：竖图在30×30选择槽内实测img为30×53.328125，长图预览520×2600，四色截图下半部分被裁。共享img参与Grid固有尺寸且ready仍留第二个placeholder轨道；最小改为既有relative容器内absolute/inset0，ready不留占位。所有10个直接组件消费者均有固定尺寸、可解析高度或aspect槽；批量执行卡无需另写比例逻辑。
3. 上述修复后，大图1倍完整，但长图小视口2倍实测 `topReachable=false`，底边与dialog视口正常。旧center缩放产生负向滚动不可达；仅将现有transform-origin改左上，不重写滚动/布局。修后横/长图四边均可达。

GenerationResultGrid为无当前消费者的旧复用入口，仅移除局部cover；不声称它是本次生产主链路。后端缩略图逻辑不改。

## 本地验证

环境：Bundled Node24.19.0、pnpm11.25.0；`pnpm install --frozen-lockfile`复用585个本地缓存包、下载0，依赖文件无变化。CI继续使用原Node22/pnpm11.19.0。

- Frontend lint通过。
- Frontend typecheck通过。
- 正式Real build通过（初次完整命令含typecheck，后续等价 `VITE_API_MODE=real vite build --mode production` 验证最终CSS，19.06秒；保留既有大chunk警告）。
- 10个相关Vitest文件28项通过（11.04秒）：Asset Content/Thumbnail/Preview/MultiSelector/Download/API、输入槽、素材Grid、批量结果树。新增/补充ready/empty/idle/loading/thumbnail-fallback/error占位与Blob释放断言。既有BatchResultTree合成图片请求的JSDOM AggregateError警告如实保留，非本次HTTP/生产请求、未改业务掩盖。
- `playwright test --config playwright.ai-images.config.ts`：真实Chromium12项全部通过（37.0秒）。横800×450、竖450×800、长320×1600、方512×512，分别覆盖选择器、即时输入/结果/大图、素材卡/详情、批量卡与生成记录；另有横/长800×650小视口2倍四边可达、切换重置1倍与下载，以及原慢图缩略回退/快速切换和失败重试。
- 不是用img方框比例代替图片比例：验证自然尺寸、computed contain/居中、容器内paint约束，并对浏览器截图解码采样四色象限。通道容差20只兼容微型槽/过渡的抗锯齿与UI状态（初见红207/35/35对220/38/38差13）；白色/背景代替下半图的真实裁切仍远超容差并失败。
- 所有HTTP由受控路由fulfill；无监听服务器、平台图像下载、付费生图、生产上传或DB。HTTPS虚拟origin保留WebCrypto能力。最初HTTP虚拟非localhost缺crypto.randomUUID导致未提交，是夹具错误，已与业务CSS失败分开核销。第一次build完成前启动测试曾缺dist，也仅为本机测试时序，不计业务负向。

截图/trace仅位于ignored `frontend/test-results/ai-image-proportions/`，不入Git。四比例preview/material和横/长small-zoom截图可供独立视觉检查。

## 门禁与交接边界

CI在既有Real build后安装锁定Chromium并执行同一12项无后端回归；本地通过不代替精确PR CI或ca97 Gate2。
原生Electron专项和真实平台/生产数据不在本次Owner证据内，不要求用户重复既有机械验收。回滚为正常revert本热修提交；无数据/Schema回退。
提交前须核git diff --check、白名单与干净工作树；不合dev/main、不发布。剩余为独立审查、精确四Job CI及Gate2。
