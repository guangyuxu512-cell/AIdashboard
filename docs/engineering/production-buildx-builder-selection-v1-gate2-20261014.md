# 生产可选 Buildx 选择工程修复 Gate 2

Owner81a1 / Integration ca97 / Release Main。当前人类明确授权最小builder配置修复，
不改业务代码、依赖或Migration；仅恢复A发布，不加入B。
候选`1677fd37d2343cb9f1e732e8f238c9a389167201`，
`feat/production-buildx-builder-selection-v1`，从A Green f5正常创建并no-ff同步
新确认治理Green`07f1cc79bb4f72776a71eddad527faef0d46016f`。
新Feature无DB/端口/服务/Migration Slot；7d55只读盘点、未参与开发或切分支。

## Gate1事实与独立审查

PR [13](https://github.com/guangyuxu512-cell/AIdashboard/pull/13)，精确CI
[38542431178](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38542431178)
已completed/success，Backend、frontend-real-build、container-runtime三项均success。
ca97独立读取实际步骤，完整Linux test-remote的新增builder和原ownership/挂载/失败归档回归已执行成功，
并有真实Runner Backend/Frontend镜像、打包上下文/Compose/只读PC+Mobile验证。
PR checkout merge `5a221bbb554a035f78d1e9cb09a1a701e7f90081` 与候选整树相同，
共同tree `003cbb5be8dcf5d3baab4a3e0d1b38fa5e73e233`，不是只核对提交说明。

ca97从精确Git归档独立检查5个相关Shell文件语法通过，完整阅读正式部署入口、受支持reader及定向测试。
本机MSYS不能证明Linux权限/符号链接语义，未把本机未跑完的完整fixture标PASS；
Windows旧临时清理被拒且命令未执行，保留ignored、不换工具绕过。Linux CI不触碰该本机路径。
上述Linux镜像验证仅Runner环境，fakeDocker部署回归的61/62是合成错误，不是生产发布或迁移。

## 精确范围与安全行为

相对07仅4文件：remote-deploy、既有test-remote、公开env示例、生产文档。
backend/frontend/mobile/Electron、平台与权限、所有依赖/Dockerfile、所有Migration、
production-env reader及CI/生产Workflow差异0；B7db不是该候选祖先。
候选敏感值匹配0、未授权artifact0、冲突0、diff错误0；配置审计不输出.env任何行。

- 复用既有非执行式production_env_read，root文件覆盖同名ambient变量。
- 缺失/空/quoted空保持旧build参数；有效单个ASCII名称以字母/数字开头，其余仅字母数字._-。
- 非空以数组追加`--builder`及单个名称，只影响build，不全局buildx use/create，不改其它run/up。
- 无效名称在Docker调用前安全退出2，不回显输入；实际build失败保留原非零，不退回默认builder盲试。
- 旧失败清理仅本次脚本拥有的新release/archive，历史/current/共享资产保护未改；不手工prune或清旧release。

6有效/空/quoted组合、10非法输入、builder失败62及原current/历史保护已由同一Linux回归执行。
`--builder`为[Compose官方build选项](https://docs.docker.com/reference/cli/docker/compose/build/)，
但官方文档和小scratch都不能证明VPS当前CLI/产物store或正式候选完整构建，仍由Main实际核验。

**工程Gate 2审查接受；正常no-ff合dev、精确CI与生产发布结果见下文。**
A原业务/视觉已验且字节未变，复用证据，不重复Electron确认。唯一B预览仍7db/0045，
不能把它当作A工程候选界面证据，也不为工程检查退回Integration0044或重载B客户端。

## Main连续发布与恢复边界

精确新Green后Main正常合入，main精确CI后走既有正式部署，范围仅A+本工程修复。
此前A main48ca680/CI已成功，但Deploy38505980435失败，旧生产0102/单一0043已恢复健康；
本工程通过前不盲重跑相同失败路径。B自然timer窗口已结束，不再阻塞VPS必要构建。

Main受保护备份及可读性验证，持久配置只设置已存在的隔离builder，保留其它配置字节/凭据，
检查实际Compose支持、builder健康与本地image store导入；不改全局默认、升级daemon或清镜像缓存。
正式A仍需原0044升级，迁移文件字节不变；新Release不含0045。
核验实际main/生产SHA、单一0044、Backend/Frontend/Signer、Real资源/无Mock、
manual selection/经营手动和每日Asia/Shanghai09:00仅昨日原配置。

有A v8或策略事实后，恢复保留兼容Reader/Schema/事实与失败审计，不能直接旧Reader回退或downgrade清历史。
任何新失败保留明确阶段/安全日志并针对原因处理，不据CI或参数smoke标DEPLOYED。
本工程无Electron字节变化，无新安装包需求；既有1.0.6及Profile保留。

## 精确合并Green与正式Release交接

正常no-ff为`af57cc3258cc4e1ab4582db57b9852956ef433f5`，父治理d4f7384与精确1677。
合后4工程payload与审查候选相同，A业务/依赖/全部Migration/CI/Electron差异0、B7db非祖先，
5Shell语法及安全检查通过；远端dev精确匹配、工作树干净。
精确[CI38547082755](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38547082755)
completed/success，三项Backend/Real build/container-runtime全部success；该SHA为正式最新Green。
后续纯治理记录不自动成为Green，不让Main追随最新dev带入B。

已交Main持续A+工程Release，不再等授权/A视觉/B模块。受保护的builder键必须在main push前
备份并设置，避免main CI后自动Deploy落回已知故障default；其它配置/密码不变。
本交接时Main实际Compose能力、builder/本地image store、新鲜DB备份/main CI/正式Deploy尚待回执。
该阶段未标DEPLOYED；后续实际完成结果如下，B原生清单独立等待用户，不混入0045。

## 精确Release与镜像源运行环境恢复

Main正常no-ff Release为`103b1c80b82f5bfca78467b887d7fafbdeb1ab60`，
其runtime/scripts/deploy/CI/依赖/Electron与af57审查范围一致、未包含B。
精确[main CI38549554911](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38549554911)
三项全部success。迁移前新鲜备份20261014T102018Z，976178 bytes，
SHA256 `a709112a1a1ff85bc19fcc2686cd60a951b79eeb1abf8ca3ad620c23ffabc950`，
restore list330通过；备份及配置副本为受保护0600文件，不登记凭据。

正式[Deploy38550018844](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38550018844)
attempt1在基础镜像registry metadata HEAD阶段出现i/o timeout/DeadlineExceeded，
没有进入pip下载，不是已证实的哈希错误、OOM、鉴权拒绝或再次daemon panic。
旧0102生产及0043正常，未切服务、未迁移，daemon未重启；失败发布目录由正式脚本清理。

只读比较确认原独立builder未继承daemon既有可信HTTPS mirror，
因此保留原builder/cache，另建仅本次任务的`control-center-a-103b1c80`，
复用该既有源、严格TLS，BuildKit镜像固定为原现存digest。
不新增未知源、不改daemon/global default、不prune、业务/依赖/Migration字节不变。
通用Python slim样本曾遇到OCI descriptor缺失，且并非正式Backend基底，未计为通过；
随后准确四个Dockerfile基底python3.12-slim-bookworm/node24-alpine/
node22-bookworm-slim/nginx1.27-alpine均真实构建并导入同一daemon store成功。
导入样本image为`sha256:6651244509bebf806e2fdb0294ec2e528ecde0db34ccea972766ae3a16883085`。

受保护仅切builder键，保留其它配置字节/凭据；只对同一精确103 Release执行一次有证据的
正式Deploy attempt2，不重跑业务CI或人工验收。构建期间不能以基础样本替代正式发布；
ca97当时独立核验旧0102/单一0043、Backend/Signer健康、Frontend运行，原配置保持。

## A正式生产发布完成（2026-10-14）

同一Deploy attempt2实际completed/success，2026-10-14北京时间20:09完成，耗时1h4m49s；
Upload and deploy release、Verify public Backend health contract均success。
正式长耗时为APT/Node及Python wheel稳步下载，没有OOM或权限拒绝，不为提速改依赖或绕校验。
Main回执已核验current、三服务tag/image ID与精确Release
`103b1c80b82f5bfca78467b887d7fafbdeb1ab60`匹配，生产
`control_center_prod`/最小应用角色、单一`20261013_0044`，未包含B0045。

ca97随后独立只读于北京时间20:35复核：active Release及Backend/Frontend/Signer均为上述完整SHA；
Backend/Signer/PG healthy、Frontend running（无container healthcheck）、重启次数0/OOM事件0，
生产Head仅0044；实际公开配置manual selection/经营manual/daily均true、09:00:00保持。
该检查业务写入/服务重启/平台请求均0。
Main用同一current正式Compose恢复Backend配置后，实际getter execution与strategy management均true；
NAS真实CIFS/mount/marker及app999:999读写执行权限通过，公网HTTPS/index及新asset200，
旧asset仍可读、缺失脚本真实404，Real产物与新image字节一致。

生产策略/Run均0；没有额外生产CRUD、新榜单、RPA或付费生成，也不把健康/配置当作新增真实业务验收。
代码未变的A集成平台与原生验收证据复用。未更换Electron/新打包，原1.0.6/Profile及B现场保留。
A及必要工程修复现标DEPLOYED；历史失败和备份、原builder/cache/卷继续保留，凭据无输出。
后续B须独立完成人工确认、Green与Release；生产已有策略/v8事实后的回退保留0044/v8 Reader及审计，
不降级清数据或直接回不兼容旧Reader。本工作树仅登记结果，不向Main额外推文档触发Deploy。
