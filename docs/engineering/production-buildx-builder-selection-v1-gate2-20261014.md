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

**工程Gate 2审查接受；正常no-ff合dev、合后精确复验与该SHA CI尚待。**
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
