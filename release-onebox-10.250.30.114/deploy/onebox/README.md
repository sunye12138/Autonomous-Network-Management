# 单容器测试版

这个目录提供一个 **单容器 onebox 测试方案**，把下面三部分一起放进一个容器：

- backend / API Server
- frontend 静态页面
- host agent

这样你在宿主机上只需要运行 **一个容器**，只打开 **一个前端页面**。

## 什么时候用这个方案
适合你现在这种场景：

- 不想让远端 Agent 去连你本机 API
- 不想开多个终端窗口
- 想先在宿主机上快速验证整套链路是否可用

## 启动方式
在宿主机项目根目录执行：

```bash
docker compose -f docker-compose.onebox.yml up -d --build
```

## 对外端口
宿主机只需要关心两个端口：

- 前端页面：`14173`
- 后端 API：`18000`

打开页面：

```text
http://服务器IP:14173/
```

健康检查：

```bash
curl http://服务器IP:18000/api/health
```

## 为什么 agent 也放进容器还能管理 Docker
因为 compose 文件里挂了：

```yaml
- /var/run/docker.sock:/var/run/docker.sock
```

并且 onebox 镜像里安装了 `docker` 命令行，所以容器内的 agent 可以直接操作宿主机 Docker。

## 常用命令
启动：

```bash
docker compose -f docker-compose.onebox.yml up -d --build
```

查看状态：

```bash
docker compose -f docker-compose.onebox.yml ps
```

查看日志：

```bash
docker compose -f docker-compose.onebox.yml logs -f
```

停止：

```bash
docker compose -f docker-compose.onebox.yml down
```

## 说明
- 这个方案适合测试和快速验证
- 如果后续要正式部署，还是建议拆成 backend / frontend / agent 多容器版本
