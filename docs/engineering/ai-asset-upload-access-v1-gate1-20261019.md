# AI上传与受限文件访问热修 Gate 1

## 范围与资源

- Owner：`hotfix/ai-asset-upload-access-v1`，工作树 `C:\Users\Administrator\.codex\worktrees\local-ssh-production-deploy\中控台`。
  从精确Green59894正常no-ff消费图片比例候选87ad1e，起点3fe41ace；最终Candidate为本记录所在功能提交，交接另报完整SHA。
- 无Schema/Migration Slot/依赖声明或版本/Electron变化。既有比例修复及证据保留，不改生成参数、Provider、通用资料库权限。
- ca97交付的受保护 `backend/.env` 只连接专用 `control_center_feat_ai_asset_upload_access`；最小角色、严格35433隧道/HBA、单一0047。
  无端口、后台服务、第二Electron、Integration/生产写入或NAS探测。ignored本地`.venv`按既有`backend[dev]`声明安装，没有更改依赖文件。

## 根因与最小修复

- Root只读生产证据：原8f内层Nginx无body限制声明，12次1.55–2.58MB请求被413拒绝，未到NAS；另4次成功Backend耗时约0.5–0.7秒、1次缺团队409。
  内层补12m与既有外层一致；Backend仍10MiB，不无限放大上限。新增真实双层代理传输回归，由原container-runtime执行。
- AI原上传/图片地址复用通用ASSET路由，AI-only会被拒绝。新增四个薄AI文件入口复用原AssetService/Storage，通用ASSET路由完全未放宽。
  AI引用资格统一守read/attach/instant+batch submit/retry，真实父聚合Team/DataScope校验；历史本人当前Team UPLOAD草稿例外明确记录，不伪称AI来源。
- 清理限定本人当前Team UPLOAD、原行锁与所有引用保护。Attach复用原FOR UPDATE并稳定UUID锁序，防止清理/关联并发FK500。
- 共享单一10MiB预检、上传专用120秒、分阶段code/requestId、HTML413明确提示；无自动重传。即时多文件逐项保留成功，Attach/清理失败分开报告。

## 本地验证与失败记录

- Backend默认非integration全量：**1065项退出0**（实际执行pytest -q叠加配置-q只显示进度；同口径collect确认1065/1512，447 deselected）。
  新资格/API及原AI服务定向58项通过；正式PG5项通过。
- 专用PG：真实SQL同Team/跨Team/伪父引用/模块撤销、无资格不能Attach/Submit制造引用、历史输入输出、Retry拒绝、ASSET原能力、清理引用保护。
  两种并发先后均通过`pg_blocking_pids`看到实际阻塞：Attach先得锁则清理ASSET_IN_USE；清理先得锁则Attach ASSET_NOT_FOUND，无悬挂引用。
- 真实ASGI+PG用有效随机JPEG（1600×1200、约2.25MB，>1MiB且<10MiB）通过原图片验证、临时Storage写入、AI内容字节一致、缩略图、正式Attach/Detach、关联中清理409、清理后404；通用列表403、撤销AI后上传403。
  人员Principal为受控夹具，真实Actor/Team/模块依赖保留；不是生产NAS/登录或Provider验收。
- Frontend全量169文件/932项通过。最后追加错误码/requestId/无重传与AI API测试后，单独两文件14项通过；不宣称先前932覆盖后写测试。
  最终lint/typecheck通过；正式Real build18.22秒通过（保留既有chunk警告）。
- 受控Production Bundle浏览器：15项38.0秒通过，覆盖原12比例/缩放/慢图/重试及AI-only上传关联预览、多文件413保留成功/刷新不重传、Attach403+Cleanup503分阶段requestId。
  四比例即时/素材及批量/历史矩阵也设为AI-only；generic文件路由显式拒绝，全部HTTP本地拦截，无监听/Backend/付费/远程图片请求。
- 修复前负向：旧上传缺专用timeout、超限仍调用POST；新AI文件路由404而非401；生产真实413与同Team-only资格缺口独立记录。
  初次PG测试错误期望历史SELF隔离而失败，按现行0037普通Team权威修正测试，未修改权限策略；大JPEG追加HTTP关联测试初次误猜Attach为201和浅层asset_id，读取既有契约后改为200/嵌套asset、Detach204，最终5项通过。
  FormData File克隆身份与JSdom未stub网络属于夹具错误，已分开核销。
- 代理脚本仅bash语法/diff/YAML四Job及内存multipart尺寸/SHA已审；**真实Linux双层Docker尚待精确PR CI，不能记为已通过**。传输接收夹具不替代上面的真实JPEG校验/Storage证据。

## 交接边界

新契约见Backend22第5节、Frontend16第8节；资源登记工程02/03。原四Job/门槛不变，只增container-runtime代理测试及扩原无后端图片回归。
Owner本地结果不是独立Gate2或生产部署。精确候选交Root独立复核与ca97，随后正式PR CI/Integration；不要求用户重复机械上传。
回退仅正常revert应用提交，无Schema/数据降级；保留AI引用/生成历史与既有资产。生产NAS耗时和真正付费任务不在本轮Owner验证范围。
