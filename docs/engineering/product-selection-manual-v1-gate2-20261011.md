# 选品手动闭环 Gate 2 与发布交接

2026-10-11；Integrator ca97；Feature Owner 81a1；Main负责正式生产操作。

## 版本与结论

Candidate `41e3116e0e176761f3a3fbb29e199283ce61c95c`，包含Green基线 `6844b3c226010abc2dafc0677407084a1958dea8`。
Gate2A ACCEPT、Gate2B PASS；no-ff Merge `3448b7d74651bcaab3f39dbeff97aee9a5fcea83`。
已确认前端父提交 `389030a54d219a75fb0b0830fd1e3ccc76235d3e`；本候选不改Vue页面结构，不重复视觉验收。
合并后Backend/Frontend/Electron/Worker/Mobile/部署文件与Candidate一致；本登记提交只改工程文档。
精确Green由本记录提交后的dev HEAD和成功CI锁定，不以本地测试代替CI。
本模块为正式手动执行；达人登录、策略保存、定时、手机及百应尚未接入，不假成功。

## 当前契约

按Asia/Shanghai接受日期D冻结七日首选[D−7,D−1]、备用[D−8,D−2]。
保留合法成功空榜一次回退；仅首选第一页精确int/string621000704、尚无事实写入时增加一次备用补查。
其他错误、后页错误或写事实后不换窗；备用失败安全记录后结束，不继续向前尝试。
该码唯一根因未确定，不普遍标记日期未就绪。后续分页/来源hash/入库/API/页面均使用实际成功scope。
复用ShopSessionAccessor→DouyinApiClient→Signer，签名Cookie与HTTP Cookie一致仅记录布尔结果。
既有授权、停用检查、回执/活动任务去重、租约屏障保留，不新增通用重试框架。

## 本候选的正式真实证据

唯一开发Electron，Real `5180 → 8100 → control_center_integration`，隔离本地Signer8787；不复制生产凭据。
现有g2_sa_v1_super启用且超级身份已核验，选定Integration团队；HuanYu平台店铺243321624，Integration ShopSession v1。

| 环节 | 结果 |
| --- | --- |
| 正式提交 | 原策略抽屉立即获取，POST `/api/v1/product-selection/runs` 202 |
| canonical run | `72f42fff-1996-4d59-9c30-30104f373e63`，succeeded/completed |
| 条件 | 短视频近7天，industry7，category `1000009092,1000009142`，默认品牌/价格，第1页10项、排名1–10 |
| 冻结范围 | 首选2026-10-04～10-10；备用2026-10-03～10-09 |
| 真实榜单 | 首选HTTP200、整数st0、10条，1次榜单请求、约1016ms |
| 事实与补充 | 10条候选/来源，10条basic_info成功，补充失败0，全部实际日期10-04～10-10 |
| source_scope_hash | `5ca29e777fe924563aa4c336ffc4b1ee1f8cf2dde0fafc7712ba9cdb59548c2d` |
| 正式查询 | GET candidates 200,total10；GET observations详情200，商品ID/last_run_id/实际日期与DB一致 |
| Real Electron | 用户回复“可见结果”，确认列表、详情及刷新；保留389前端视觉确认 |
| 刷新 | 前后canonical run4、事实10、活动任务0；新增run0、榜单/basic_info/Signer请求0，列表仍10 |
| 历史保留 | 之前3个失败run仍failed；先前只读备用诊断不入库、不冒充本run |

本次首选已有数据，**此正式run未触发备用**。此前同条件首选621000704、备用st0/10条只是日期对照。
自动回退的选窗/分页/事实/API/幂等/租约/授权由真实PostgreSQL加合成平台验证；不重复平台强造回退，也不隐去该证据边界。

## 检查

| 检查 | 结果与边界 |
| --- | --- |
| ca97 Backend默认回归 | 595 PASS，默认排除integration，非全量PG |
| ca97 Frontend lint/typecheck/Real build | PASS，生产Mock marker匹配0 |
| ca97 Frontend完整unit | 137文件/580 PASS；既有Home/jsdom XHR警告保留，未改依赖 |
| ca97 定向unit | 10文件/59 PASS |
| ca97 Real浏览器E2E | 2 PASS，API全部拦截，不当作原生/实际平台证据 |
| ca97 Integration兼容PG | 81 PASS、0失败/错误/skip；真实共享DB、平台合成，排除4个要求空库唯一super的用例，不修改既有账号 |
| Owner Feature PG | 85个唯一用例PASS，包含上述空Feature专用4项、迁移约束；不冒充ca97独立85项 |
| 合并后Backend复验 | 45 PASS，request mapping、DouyinApiClient、source，无平台调用 |
| 字节与安全审计 | 1485tracked blobs一致、11项仓库声明CMD行尾转换；本地敏感值仅内存比较，凭据匹配0、禁入文件0、diff-check PASS |

首次共享PG79PASS/6FAIL：旧集成执行器抢走合成pending任务，以及4个空库super夹具不适合现有共享库。
停止已核对的旧执行器后重跑81项成功；不修改测试/候选，不提权或撤销现有超级账号。
合成夹具残留0；正式10条事实与失败历史保留；本地配置、日志、JUnit、snapshot ignored。
原生自动截图/坐标点击受限，由用户实际操作补齐读取确认，不用网页截图冒充原生窗口。

## Migration与Release

Integration `20260924_0041 → 20261010_0042 → 20261010_0043`、单一Head0043；原文件字节不变。
0042 SHA-256 `8d6a9b7dab785cc470f51bcbc30ee87dec47bc98edde9747bc52a3a792646316`；
0043 SHA-256 `ecf528848d5ed9689b9b31b43715be44fd8ffd599375821672e6f735c6bb6733`。
两项串行Slot统一released，Feature库retained；不据此继续新增Migration。
正式有run后禁止0043 downgrade/清库。回退使用v2兼容Reader并关闭新执行，保留Schema/事实/失败历史。
用户已授权通过Green CI后发布本模块，不等待达人/定时。Main先核对完整范围、干净工作树、迁移前新备份及pg_restore可读性、磁盘与服务。
main成功CI自动Deploy只执行一次；0041向前升级0042/0043、启用正式手动执行，保留经营每日09:00配置。
不复制Integration夹具/账号/Session；交接时未main合并或部署，实际版本/健康/0043/Real/API核验后才登记DEPLOYED。
