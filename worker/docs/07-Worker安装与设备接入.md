# Worker 安装与设备接入

Worker 是 Windows 执行程序，中控界面通过 Web 访问。Worker 在与 RPA 相同的 Windows 用户下读取本机 RPA 保存的店铺资料，向中控报告设备、技能、店铺和会话状态；中控不接收店铺 Session。

## 地址和预检

中控与独立商品库分别配置。Worker 从中控领取任务，商品库预检结果直接回传商品库。非生产环境必须显式配置各自的测试地址，不能把正式地址当测试入口。每设备最多并发五个店铺、每店最多三个预检；平台明确的登录失效才跳过该店，网络或其他错误不标记登录失效。

## 构建

使用受信任的正式能力包签名公钥文件构建，私钥不进入发行包：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-worker.ps1 -CapabilityPublicKeyFile <受保护位置>\capability-public-key.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-worker-package.ps1
```

构建机可设置 `WORKER_BUILD_PYTHON` 指向项目兼容的 Worker Python 环境；不设置时使用 `worker/.venv`。打包检查只检查发行文件、程序版本及公钥，不连接生产、不修改真实设备。

## 接入与升级

首次接入在中控设备中心签发该设备的 Worker Token，在 Worker 窗口填写并启动。从 0.5.8 开始，Worker 使用设备身份向中控检查底座版本：执行中的任务结束、待回传结果和事件完成后，才切换到验签的新版本。安装在独立目录，不修改已有设备绑定、受保护配置和 RPA 店铺资料。新版启动并完成认证心跳前不领取任务；启动失败时恢复旧版，同一失败版本不会反复切换，发布方可以递增签名清单序号后再次发布。

现有 0.5.5 不具备底座自更新入口，首次接入这套机制需要通过现有安装方式切换一次；不需要重新绑定或重新登录店铺。此后从支持自更新的版本升级，不需要逐台手动安装。原始启动入口再次启动时，会校验并使用已启用的新版。

底座和技能包分别使用签名清单。底座发行包由发布机使用受保护私钥签名，发布到中控受保护的发行目录；Worker 通过设备认证从中控下载并校验签名、摘要和文件。Worker 不访问 GitHub、不持有 GitHub 凭据，仓库是否私有不影响设备更新。清单中的序号必须递增，错误签名、旧序号或损坏包不会替换旧版。

不要将 Token、Session、Cookie、数据库凭据或私钥放入仓库、发行包和日志。
