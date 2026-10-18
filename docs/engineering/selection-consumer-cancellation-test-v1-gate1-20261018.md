# 选品消费者取消竞态 CI 热修 Gate 1

## 结论与边界

- 精确 Green：`1cec344b72621b9e50ed3e724e939623e7d366e4`；分支：
  `hotfix/selection-consumer-cancellation-test-v1`。
- Main CI `39131501325`（Head `36dbc5ff5009619fa0052f5da06f53383f223329`）只有 Backend Job
  失败；`verify-offline`、`container-runtime` 与 `frontend-real-build` 均成功。
- 唯一失败是
  `test_enabled_confirmed_consumer_uses_existing_executor[3]`：期望三个消费者均完成首轮调用，实际只观察到
  两次。原测试在任一消费者进入空闲等待时立即抛出 `CancelledError`，因此 `gather` 可以在其余消费者完成
  首轮调度前传播取消。
- 本热修只在测试中增加首轮 `Barrier`。确认映射的消费者先全部调用 `execute_available`，未确认映射的
  相邻消费者先全部调用 `recover_only`，之后才允许模拟空闲等待触发取消。
- 生产 `run_executor.py`、容量 3、真实并发断言、Scheduler、执行器、CI 配置及选品 A/B 业务代码均未修改；
  没有用时间延迟、减少 worker 数或削弱断言掩盖竞态。

## 失败证据与本机边界

GitHub Backend Job `117687444882` 在 Python 3.12.15 上留下精确断言：
`[True, True] != [True, True, True]`，失败行是原测试的容量断言。Windows 本机修前单次运行及同一生产协程
500 轮压力运行没有复现该调度顺序；这不推翻 Hosted CI 的真实失败，也不写成“本机已复现”。修复采用
同步先决条件消除调度顺序依赖，而不是依赖增加随机重复次数。

## Gate 1 验证

| 检查 | 结果 |
| --- | --- |
| 两个消费者测试、容量 1/3 | 4 passed |
| 同一组测试独立进程重复 10 轮 | 10/10 通过，共 40 个参数化用例，无失败 |
| `pytest backend/tests/test_selection_connector.py -q` | 19 passed |
| `pytest tests -k selection -q` | 557 passed；仅既有 Starlette/httpx warning |
| Backend 默认离线 `pytest -q` | 1053 passed、442 integration deselected；仅既有 warning |
| `python -m compileall -q app tests` | exit 0 |
| `git diff --check` | exit 0 |

原 Main CI 的 disposable PostgreSQL Job 已执行到完整 Backend 测试后才命中此测试竞态；本 Feature Owner
没有重跑 Hosted CI、连接数据库或重复已通过的其它 Jobs。新候选的 Hosted CI 由 ca97 在 Gate 2 合入后核验。

## 交接与回退

- 无 Schema、Migration、数据库、配置、依赖、端口、Electron、平台请求或生产动作。
- ca97 只需独立复核测试屏障不会改变生产实现，并运行相邻消费者测试；通过后按原流程处理精确 CI。
- 回退仅需回退本热修提交；没有数据或运行状态恢复步骤。
