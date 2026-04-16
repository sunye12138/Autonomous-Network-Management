from __future__ import annotations


class SSHService:
    def __getattr__(self, name: str):
        raise RuntimeError("当前架构已切换为 Host Agent 模式，不再通过 SSH 直接执行运维操作")


ssh_service = SSHService()
