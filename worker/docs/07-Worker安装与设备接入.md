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

首次接入在中控设备中心签发该设备的 Worker Token，在 Worker 窗口填写并启动。升级前等待当前任务结束并停止旧版本，在新目录启动；继续使用原 Windows 用户及已有设备身份配置，不清空 RPA 资料，也不要求重新登录店铺。底座更新与签名能力包自动更新是两回事。

不要将 Token、Session、Cookie、数据库凭据或私钥放入仓库、发行包和日志。
