# Linux Onebox 安装包（10.250.30.114）

本安装包面向 Linux 服务器 **10.250.30.114**。

## 预置说明
- 制品库存储路径：`/mnt/dockerContainerSave/image`
- 预置服务器：`10.250.30.101` ~ `10.250.30.106`
- 已启用 Ping 检测，可用于区分“主机网络可达”和“Agent 在线状态”。

## 包含内容
- 后端 API
- 客户 Portal 页面 `portal.html`
- 根路径自动跳转到 `portal.html`
- onebox 的 `start / stop / status / rebuild` 脚本

## 启动
```bash
cd /root/server-manager/release-onebox-10.250.30.114
chmod +x start.sh stop.sh status.sh rebuild.sh ./deploy/onebox/*.sh
HOST_DOCKER_BIN=$(which docker) ./start.sh
```

## 重建
```bash
cd /root/server-manager/release-onebox-10.250.30.114
chmod +x start.sh stop.sh status.sh rebuild.sh ./deploy/onebox/*.sh
HOST_DOCKER_BIN=$(which docker) ./rebuild.sh
```

## 访问地址
- Portal：`http://10.250.30.114:14173/` 或 `http://10.250.30.114:14173/portal.html`
- 旧入口：`http://10.250.30.114:14173/index.html`，会自动跳转到 Portal
- 健康检查：`http://10.250.30.114:18000/api/health`
