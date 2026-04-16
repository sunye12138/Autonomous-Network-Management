from __future__ import annotations

import ctypes
import getpass
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api").rstrip("/")
AGENT_ID = os.getenv("AGENT_ID")
AGENT_NAME = os.getenv("AGENT_NAME") or socket.gethostname()
HOST_ADDRESS = os.getenv("HOST_ADDRESS") or socket.gethostname()
MANAGEMENT_IP = os.getenv("MANAGEMENT_IP") or os.getenv("MANAGEMENT_ADDRESS") or HOST_ADDRESS
HOST_IP = os.getenv("HOST_IP") or HOST_ADDRESS
AGENT_VERSION = os.getenv("AGENT_VERSION", "0.3.0")
DEFAULT_POLL_INTERVAL = float(os.getenv("AGENT_POLL_INTERVAL", "3"))
DEFAULT_HEARTBEAT_INTERVAL = float(os.getenv("AGENT_HEARTBEAT_INTERVAL", "15"))
CLAIM_LIMIT = int(os.getenv("AGENT_CLAIM_LIMIT", "5"))
COMMAND_TIMEOUT_SECONDS = int(os.getenv("AGENT_COMMAND_TIMEOUT_SECONDS", "1800"))
PROFILE_CACHE_SECONDS = float(os.getenv("AGENT_PROFILE_CACHE_SECONDS", "5"))
CAPABILITIES = [
    item.strip()
    for item in os.getenv(
        "AGENT_CAPABILITIES",
        "docker.list_containers,docker.list_images,docker.container_action,docker.container_logs,artifact.export_image,artifact.import_image,deploy.compose_bundle",
    ).split(",")
    if item.strip()
]


class AgentHttpError(RuntimeError):
    pass


class HostAgent:
    def __init__(self) -> None:
        if not AGENT_ID:
            raise ValueError("Missing AGENT_ID environment variable")
        self.poll_interval = DEFAULT_POLL_INTERVAL
        self.heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL
        self._profile_cache: Optional[Dict[str, Any]] = None
        self._profile_cache_at = 0.0

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        url = f"{API_BASE_URL}{path}"
        request_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise AgentHttpError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise AgentHttpError(f"Request failed: {exc.reason}") from exc

    def _apply_intervals(self, response: Any) -> None:
        if not isinstance(response, dict):
            return
        heartbeat_value = response.get("heartbeat_interval_seconds")
        poll_value = response.get("poll_interval_seconds")
        if isinstance(heartbeat_value, (int, float)) and heartbeat_value > 0:
            self.heartbeat_interval = float(heartbeat_value)
        if isinstance(poll_value, (int, float)) and poll_value > 0:
            self.poll_interval = float(poll_value)

    def _linux_cpu_percent(self) -> Optional[float]:
        stat_path = Path("/proc/stat")
        if not stat_path.exists():
            return None

        def read_cpu_times() -> Optional[Tuple[int, int]]:
            try:
                first_line = stat_path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
                parts = [int(item) for item in first_line.split()[1:]]
                total = sum(parts)
                idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
                return total, idle
            except Exception:
                return None

        start = read_cpu_times()
        if not start:
            return None
        time.sleep(0.12)
        end = read_cpu_times()
        if not end:
            return None
        total_delta = end[0] - start[0]
        idle_delta = end[1] - start[1]
        if total_delta <= 0:
            return None
        return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 2)

    def _linux_memory_info(self) -> Tuple[Optional[int], Optional[int], Optional[float]]:
        meminfo_path = Path("/proc/meminfo")
        if not meminfo_path.exists():
            return None, None, None
        values: Dict[str, int] = {}
        try:
            for line in meminfo_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if ":" not in line:
                    continue
                key, raw_value = line.split(":", 1)
                parts = raw_value.strip().split()
                if not parts:
                    continue
                values[key] = int(parts[0]) * 1024
        except Exception:
            return None, None, None

        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return None, None, None
        used = max(total - available, 0)
        percent = round((used / total) * 100, 2) if total else None
        return total, used, percent

    def _windows_cpu_percent(self) -> Optional[float]:
        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

        def as_int(value: FILETIME) -> int:
            return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)

        def read_times() -> Optional[Tuple[int, int, int]]:
            idle = FILETIME()
            kernel = FILETIME()
            user = FILETIME()
            if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                return None
            return as_int(idle), as_int(kernel), as_int(user)

        start = read_times()
        if not start:
            return None
        time.sleep(0.12)
        end = read_times()
        if not end:
            return None

        idle_delta = end[0] - start[0]
        kernel_delta = end[1] - start[1]
        user_delta = end[2] - start[2]
        total_delta = kernel_delta + user_delta
        if total_delta <= 0:
            return None

        busy = max(total_delta - idle_delta, 0)
        percent = (busy / total_delta) * 100
        return round(max(0.0, min(100.0, percent)), 2)

    def _windows_memory_info(self) -> Tuple[Optional[int], Optional[int], Optional[float]]:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None, None, None

        total = int(status.ullTotalPhys)
        available = int(status.ullAvailPhys)
        used = max(total - available, 0)
        percent = round((used / total) * 100, 2) if total else None
        return total, used, percent

    def _cpu_percent(self) -> Optional[float]:
        if os.name == "nt":
            return self._windows_cpu_percent()
        return self._linux_cpu_percent()

    def _memory_info(self) -> Tuple[Optional[int], Optional[int], Optional[float]]:
        if os.name == "nt":
            return self._windows_memory_info()
        return self._linux_memory_info()

    def _os_name(self) -> str:
        os_release = Path("/etc/os-release")
        if os_release.exists():
            try:
                for line in os_release.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
            except Exception:
                pass
        return platform.platform()

    def _runtime_name(self) -> Optional[str]:
        exit_code, output, error = self._run_command(["docker", "--version"], timeout=20)
        if exit_code != 0:
            return self._combined_output(output, error) or None
        return output.strip() or None

    def _collect_host_profile(self, *, force: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        if not force and self._profile_cache and now - self._profile_cache_at < PROFILE_CACHE_SECONDS:
            return dict(self._profile_cache)

        memory_total, memory_used, memory_percent = self._memory_info()
        profile = {
            "host": MANAGEMENT_IP,
            "management_ip": MANAGEMENT_IP,
            "host_ip": HOST_IP,
            "reported_user": getpass.getuser(),
            "os_name": self._os_name(),
            "runtime": self._runtime_name(),
            "version": AGENT_VERSION,
            "capabilities": CAPABILITIES,
            "cpu_percent": self._cpu_percent(),
            "memory_percent": memory_percent,
            "memory_total_bytes": memory_total,
            "memory_used_bytes": memory_used,
        }
        self._profile_cache = dict(profile)
        self._profile_cache_at = now
        return profile

    def register(self) -> None:
        payload = self._collect_host_profile(force=True)
        payload.update({
            "agent_id": AGENT_ID,
            "name": AGENT_NAME,
        })
        response = self._request_json("POST", "/agents/register", payload)
        self._apply_intervals(response)

    def heartbeat(self) -> None:
        response = self._request_json("POST", f"/agents/{AGENT_ID}/heartbeat", self._collect_host_profile())
        self._apply_intervals(response)

    def claim_tasks(self) -> List[Dict[str, Any]]:
        payload = self._collect_host_profile()
        payload["limit"] = CLAIM_LIMIT
        data = self._request_json("POST", f"/agents/{AGENT_ID}/tasks/claim", payload)
        return data.get("tasks", []) if isinstance(data, dict) else []

    def complete_task(self, task_id: int, success: bool, result: Any = None, error: Optional[str] = None) -> None:
        self._request_json(
            "POST",
            f"/agents/{AGENT_ID}/tasks/{task_id}/complete",
            {
                "success": success,
                "result": result,
                "error": error,
            },
        )

    def _combined_output(self, output: str, error: str) -> str:
        parts = [part.strip() for part in (output, error) if part and part.strip()]
        return "\n".join(parts)

    @staticmethod
    def _decode_output(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def _run_command(
        self,
        args: List[str],
        *,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, str, str]:
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=False,
                check=False,
                cwd=str(cwd) if cwd else None,
                timeout=timeout or COMMAND_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            return 127, "", str(exc)
        except subprocess.TimeoutExpired as exc:
            stdout = self._decode_output(exc.stdout)
            stderr = self._decode_output(exc.stderr)
            return 124, stdout, stderr or "command timeout"
        return (
            completed.returncode,
            self._decode_output(completed.stdout),
            self._decode_output(completed.stderr),
        )

    def _download_file(self, path: str, destination: Path) -> None:
        request = urllib.request.Request(f"{API_BASE_URL}{path}", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as file_obj:
                shutil.copyfileobj(response, file_obj)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise AgentHttpError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise AgentHttpError(f"Request failed: {exc.reason}") from exc

    def _get_artifact_metadata(self, artifact_id: int) -> Dict[str, Any]:
        data = self._request_json("GET", f"/artifacts/{artifact_id}")
        if not isinstance(data, dict):
            raise AgentHttpError("Invalid artifact metadata response")
        return data

    def _upload_artifact(self, file_path: Path, *, file_name: str, kind: str) -> Dict[str, Any]:
        request = urllib.request.Request(
            f"{API_BASE_URL}/artifacts/upload",
            data=file_path.read_bytes(),
            headers={
                "Content-Type": "application/octet-stream",
                "X-Artifact-Name": urllib.parse.quote(file_name),
                "X-Artifact-Kind": urllib.parse.quote(kind),
                "X-Artifact-Source": urllib.parse.quote(f"agent:{AGENT_ID}"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise AgentHttpError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise AgentHttpError(f"Request failed: {exc.reason}") from exc

    def _default_export_name(self, image_ref: str) -> str:
        safe_name = image_ref.replace("/", "_").replace(":", "_")
        return f"{safe_name}.tar"

    def _safe_join(self, root: Path, relative: Optional[str], *, error_label: str) -> Tuple[Optional[Path], Optional[str]]:
        if not relative:
            return root, None
        candidate = (root / relative).resolve()
        root_resolved = root.resolve()
        if candidate != root_resolved and root_resolved not in candidate.parents:
            return None, f"{error_label} 瓒呭嚭浜嗗厑璁哥殑鐩綍鑼冨洿"
        return candidate, None

    def _list_containers(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        exit_code, output, error = self._run_command(["docker", "ps", "-a", "--format", "{{json .}}"])
        if exit_code != 0:
            return False, None, self._combined_output(output, error) or "docker ps failed"

        containers: List[Dict[str, Any]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            containers.append(
                {
                    "id": item.get("ID", ""),
                    "name": item.get("Names", ""),
                    "image": item.get("Image", ""),
                    "status": item.get("Status", ""),
                    "state": item.get("State"),
                    "ports": item.get("Ports"),
                    "running_for": item.get("RunningFor"),
                }
            )
        return True, {"containers": containers}, None


    def _list_images(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        exit_code, output, error = self._run_command(["docker", "image", "ls", "--digests", "--format", "{{json .}}"])
        if exit_code != 0:
            return False, None, self._combined_output(output, error) or "docker image ls failed"

        images: List[Dict[str, Any]] = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            repository = item.get("Repository") or "<none>"
            tag = item.get("Tag") or "<none>"
            image_id = item.get("ID") or ""
            reference = f"{repository}:{tag}" if repository != "<none>" and tag != "<none>" else image_id
            digest = item.get("Digest")
            if digest == "<none>":
                digest = None
            images.append(
                {
                    "id": image_id,
                    "repository": repository,
                    "tag": tag,
                    "reference": reference,
                    "digest": digest,
                    "created_since": item.get("CreatedSince"),
                    "created_at": item.get("CreatedAt"),
                    "size": item.get("Size"),
                }
            )
        return True, {"images": images}, None

    def _container_action(self, action: str, container_name: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if action not in {"start", "stop", "restart"}:
            return False, None, f"Unsupported docker action: {action}"
        if not container_name:
            return False, None, "Missing container_name"
        exit_code, output, error = self._run_command(["docker", action, container_name])
        if exit_code != 0:
            return False, None, self._combined_output(output, error) or f"docker {action} failed"
        return True, {
            "success": True,
            "message": output.strip() or f"docker {action} succeeded",
            "container_name": container_name,
        }, None

    def _container_logs(self, container_name: str, tail: int) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if not container_name:
            return False, None, "Missing container_name"
        exit_code, output, error = self._run_command(["docker", "logs", "--tail", str(tail), container_name])
        if exit_code != 0:
            return False, None, self._combined_output(output, error) or "docker logs failed"
        return True, {"container_name": container_name, "logs": self._combined_output(output, error)}, None

    def _export_image(self, image_ref: str, artifact_name: Optional[str]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if not image_ref:
            return False, None, "Missing image_ref"
        export_name = artifact_name or self._default_export_name(image_ref)
        with tempfile.TemporaryDirectory(prefix="host-agent-export-") as temp_dir:
            export_path = Path(temp_dir) / export_name
            exit_code, output, error = self._run_command(
                ["docker", "image", "save", "-o", str(export_path), image_ref],
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            if exit_code != 0:
                return False, None, self._combined_output(output, error) or "docker image save failed"
            artifact = self._upload_artifact(export_path, file_name=export_name, kind="docker-image")
        return True, {
            "message": f"Image {image_ref} exported to artifact store",
            "image_ref": image_ref,
            "artifact_id": artifact.get("id"),
            "artifact_name": artifact.get("file_name"),
            "size_bytes": artifact.get("size_bytes"),
        }, None

    def _import_image(self, artifact_id: int) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if artifact_id <= 0:
            return False, None, "Missing artifact_id"
        metadata = self._get_artifact_metadata(artifact_id)
        file_name = metadata.get("file_name") or f"artifact-{artifact_id}.tar"
        with tempfile.TemporaryDirectory(prefix="host-agent-import-") as temp_dir:
            artifact_path = Path(temp_dir) / file_name
            self._download_file(f"/artifacts/{artifact_id}/download", artifact_path)
            exit_code, output, error = self._run_command(
                ["docker", "load", "-i", str(artifact_path)],
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            if exit_code != 0:
                return False, None, self._combined_output(output, error) or "docker load failed"
        return True, {
            "message": f"闀滃儚鍖?{file_name} 瀵煎叆鎴愬姛",
            "artifact_id": artifact_id,
            "output": self._combined_output(output, error),
        }, None

    def _deploy_compose_bundle(
        self,
        artifact_id: int,
        project_name: Optional[str],
        compose_file: str,
        workdir: Optional[str],
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        if artifact_id <= 0:
            return False, None, "Missing artifact_id"
        metadata = self._get_artifact_metadata(artifact_id)
        file_name = metadata.get("file_name") or f"artifact-{artifact_id}.tar"
        with tempfile.TemporaryDirectory(prefix="host-agent-deploy-") as temp_dir:
            archive_path = Path(temp_dir) / file_name
            extract_dir = Path(temp_dir) / "bundle"
            extract_dir.mkdir(parents=True, exist_ok=True)
            self._download_file(f"/artifacts/{artifact_id}/download", archive_path)
            try:
                shutil.unpack_archive(str(archive_path), str(extract_dir))
            except (shutil.ReadError, ValueError) as exc:
                return False, None, f"瑙ｅ帇閮ㄧ讲鍖呭け璐? {exc}"

            deploy_dir, error_message = self._safe_join(extract_dir, workdir, error_label="workdir")
            if error_message:
                return False, None, error_message
            if deploy_dir is None or not deploy_dir.exists():
                return False, None, "Deployment directory does not exist"

            compose_path, error_message = self._safe_join(deploy_dir, compose_file, error_label="compose_file")
            if error_message:
                return False, None, error_message
            if compose_path is None or not compose_path.exists():
                return False, None, f"Compose 鏂囦欢涓嶅瓨鍦? {compose_file}"

            command = ["docker", "compose"]
            if project_name:
                command.extend(["-p", project_name])
            command.extend(["-f", str(compose_path), "up", "-d"])
            exit_code, output, error = self._run_command(
                command,
                cwd=deploy_dir,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            if exit_code != 0:
                return False, None, self._combined_output(output, error) or "docker compose up failed"

        return True, {
            "message": f"Compose 鍖?{file_name} 閮ㄧ讲鎴愬姛",
            "artifact_id": artifact_id,
            "project_name": project_name,
            "compose_file": compose_file,
            "output": self._combined_output(output, error),
        }, None

    def execute_task(self, task: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        task_type = task.get("task_type")
        payload = task.get("payload") or {}
        if task_type == "docker.list_containers":
            return self._list_containers()
        if task_type == "docker.list_images":
            return self._list_images()
        if task_type == "docker.container_action":
            return self._container_action(str(payload.get("action", "")).strip(), str(payload.get("container_name", "")).strip())
        if task_type == "docker.container_logs":
            return self._container_logs(str(payload.get("container_name", "")).strip(), int(payload.get("tail", 200)))
        if task_type == "artifact.export_image":
            return self._export_image(str(payload.get("image_ref", "")).strip(), payload.get("artifact_name"))
        if task_type == "artifact.import_image":
            return self._import_image(int(payload.get("artifact_id", 0)))
        if task_type == "deploy.compose_bundle":
            return self._deploy_compose_bundle(
                int(payload.get("artifact_id", 0)),
                str(payload.get("project_name") or "").strip() or None,
                str(payload.get("compose_file") or "docker-compose.yml").strip() or "docker-compose.yml",
                str(payload.get("workdir") or "").strip() or None,
            )
        return False, None, f"Unsupported task type: {task_type}"

    def run(self) -> None:
        print(f"[INFO] Host Agent starting: id={AGENT_ID}, api={API_BASE_URL}")
        last_heartbeat = 0.0
        while True:
            try:
                now = time.monotonic()
                if now - last_heartbeat >= self.heartbeat_interval:
                    self.register()
                    self.heartbeat()
                    last_heartbeat = now
                tasks = self.claim_tasks()
                if not tasks:
                    time.sleep(self.poll_interval)
                    continue
                for task in tasks:
                    task_id = task["id"]
                    task_type = task["task_type"]
                    print(f"[INFO] Executing task #{task_id}: {task_type}")
                    success, result, error = self.execute_task(task)
                    self.complete_task(task_id, success=success, result=result, error=error)
            except Exception as exc:
                print(f"[ERROR] Agent loop failed: {exc}", file=sys.stderr)
                time.sleep(max(self.poll_interval, 3.0))


if __name__ == "__main__":
    try:
        HostAgent().run()
    except Exception as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        raise SystemExit(1)
