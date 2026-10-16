# MyCookLab Session 刷新诊断 Gate 2

## 当前状态

精确候选`229d5c6ca41be1e4fe45fd12caee4b2f988a95c6`独立Gate 2通过，
待正常no-ff集成、合后复验与精确dev CI；此状态只针对后端诊断，不通过98 UI或原生产故障。
81a1负责独立后端候选，ca97负责集成及精确dev CI，Main负责Release Gate和正式部署。生产目前为
`21229eff5ddf9900b8f38b13c89382952f90ee7b`，单一Head为`20261015_0046`。

2026-10-17人类在规划会话的原始turn
`01a145b7-e9d3-73e2-8400-ab1f43dd8dfd`确认完整最小范围：独立后端安全诊断、
排除未获生产授权的cleanup、正常三服务部署，以及健康后MyCookLab一次正常登录取证。
本次不是98反馈UI或1.0.7客户端发布，不代表旧失败根因已经查明。

## 基线与资源

Owner分支为`feat/shop-session-payload-diagnostics-v1`，基线为已发布Green
`1773a97d27c56512a620337e3259cceabadca2f1`。该提交与生产21229的完整
Backend、Frontend、Electron、package及lock文件应用树一致。

只分配源码、Fake仓储和内存ASGI验证。不连接Feature、Integration或生产DB实施测试，
不申请新DB、端口、后台服务、Migration Slot或安装包。旧0043 Feature库继续保留，
不升级或借用；98候选及当前Real集成Electron、Profile、人员会话和店铺Session保留。
生产只读核查走原受信任SSH及只读事务，任何新平台请求均须等候下面的正式取证门禁。

## 发布范围

运行代码仅限Session的`refresh_service.py`、`health_service.py`和`api.py`。
配套现有refresh/health测试、新增API诊断测试，以及Backend文档10和19；正常Handoff与Gate记录另计。
不修改认证、店铺身份、租约、版本CAS、重试、原事务或采集规则。

诊断只输出固定stage、固定验证子步骤、最多3条已知Schema字段类别和类型及截断标记。
新domain WARNING只接受UUID形状的原request_id，其他值省略或使用固定unavailable。
禁止输出异常repr、traceback、Pydantic input/msg/ctx、原始loc、Cookie名称/值、身份原值、
请求体、完整URL、请求头或任意details。保留原HTTP状态、错误码和消息；旧1.0.6客户端兼容。
进入Connector不证明HTTP已经发出，未知或多项问题不得被解释为唯一根因。

现有98/a488的stage只返回在错误响应中；原request logger不记录details，旧1.0.6 Main也不保留stage。
本次必须验证新的后端domain WARNING确实进入既有受保护stdout/stderr，不能只测投影函数返回值。

## Cleanup 排除

授权撤销的merge为`5131c61b38925cc3bf38f5cc02359aee2e1ebcf7`，其第一父为
`03d67370d1add7b521124b8648f37464786d0808`。ca97在干净dev执行正常
`git revert --no-edit -m 1`，产生`a1df17e9e923c73a17a129f148a6267dc83191fe`。
应用树与生产21229的净差异为零，原cleanup分支、1aec/5a提交及共享stash均保留。
这次revert与后续治理记录都不是Green，也未改变当前独立预览源码。

诊断通过后按正常no-ff合入dev并复验、推送精确SHA等待CI。Main必须确认相对21229
的净运行差异只有已批准诊断，不含cleanup四路径、98 UI、商品数据、配置、依赖或Migration。
不允许Feature直接合main或以本地测试代替CI。

## Gate 2 验证结果

候选唯一直接父为1773，远端交付SHA一致。精确范围为批准8路径加Gate 1记录，
9份归档blob校验无差异；Frontend、Electron、Core、平台、Migration、package和lock与生产完全相同。

ca97独立执行七文件104项全部通过，真实HTTP transport与SQLAlchemy连接均设拒绝哨兵。
另有独立内存ASGI/实际默认stderr日志出口16项通过：七stage、三子步骤、未知/缺失stage、
恶意额外details、不合法请求ID、成功及非目标码均符合契约。响应、domain和原access日志合法UUID关联一致，
新日志无合成秘密标记，API每次只调用service一次。该探针在旧98响应stage实现上准确失败于缺失domain日志，
是本次日志出口的负向对照，不是生产平台证据。

AST逐项核对原`acquire/release/complete`、`check/apply_response_cookie_updates`及保存/resume/return尾部不变。
仅展开三个固定诊断catch后的候选验证成功路径与基线一致。初版本机AST探针只展开顶层try，
漏掉Cookie merge的嵌套try；保留初次结果后修正为只递归展开三个固定catch，候选源码未改。
无禁入临时路径，无服务、DB、真实平台或客户端操作。

以下门槛均已按上述范围验证；合并后仍需复验净差异与相同测试，并等待精确CI。

- 独立核对精确Candidate、父链、8路径范围与契约，不使用Owner HEAD代替交付SHA。
- 新候选定向测试覆盖七stage、验证子步骤、Schema有界投影及旧Session/lease/CAS保护。
- 内存ASGI及实际日志出口验证原500/code/message、响应/domain/access的request_id关联。
- 未知值、恶意字段、无效request_id和合成敏感canary不能进入新诊断日志。
- 成功及非目标错误不产生本次失败诊断；上下文失败不调用Connector，进入Connector不伪称已发HTTP。
- 合并后复验相同边界与净差异，工作树干净、临时材料被忽略，再等待精确dev CI。

既有27项Backend Fake测试及旧stage探针仅作为基础证据，不能代替尚未交付候选的新日志验证。
未改变的前端、Electron和HuanYu人工验收直接复用，不重复登录或取数。

## 生产取证门禁

只读核查确认生产三服务为21229，Backend/Signer健康，Frontend运行且未配置独立healthcheck。
MyCookLab仍valid v1，无活动refresh lease。2026-10-16上海21:25:01、21:25:13、21:25:42
三次refresh均为500/`SHOP_SESSION_PAYLOAD_INVALID`，旧记录缺少stage，不能事后猜测具体分支。

当前该店paused、pending、running、经营边界前未执行项及昨日pending均为0；
历史failed 19项、succeeded 125项保持。手动执行与每日采集均开启，每日时间为Asia/Shanghai 09:00。
这些是准备时快照，正式点击前必须重新核查；版本、lease或三类潜在恢复范围变化即停止回报。

诊断正式部署健康后，先向规划提供就绪通知，随后仅由用户对MyCookLab点击一次正常“登录”。
不代点、不额外调用refresh，不另点验证会话，不贴Cookie，最多一次refresh POST。
正常流程会获取/释放租约；通过权威验证时会保存加密Session、递增版本并更新采集/验证时间。
原成功逻辑还可能skip/resume/defer原采集Item并更新Job，因此不是只读操作；
本次只允许保持零值门禁后的原正常流程，不手写业务表、改开关或扩大补采。

失败后立即按request_id提取安全日志及前后元数据，保留旧Session和失败历史，不自动重试。
未复现时如实记录未复现，不倒推历史根因；未知、多字段和Connector实际HTTP未证实的边界必须保留。

## 部署与回滚

现有正式脚本会build/up Backend、Frontend和Signer；净代码变化仅Backend诊断，
Frontend/Signer代码及配置不变，但正常服务替换可能短暂中断。例行alembic upgrade head预期在0046无操作。
需要回滚时使用正式21229镜像或正常revert，保留0046、Profile、已成功的新Session和全部业务数据。
不降库，不回写旧Session；回滚前保留此次安全诊断证据。

原始脱敏证据、批准范围及临时验证材料位于本机ignored
`.codex/shop-login-production-diagnostic-preparation-20261017/`，不提交日志、PID或机密配置。
