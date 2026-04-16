const apiBaseInput = document.getElementById("apiBaseInput");
const saveApiBtn = document.getElementById("saveApiBtn");
const healthBtn = document.getElementById("healthBtn");
const refreshOverviewBtn = document.getElementById("refreshOverviewBtn");
const statusText = document.getElementById("statusText");
const overviewCards = document.getElementById("overviewCards");
const serverForm = document.getElementById("serverForm");
const refreshServersBtn = document.getElementById("refreshServersBtn");
const serversTableBody = document.getElementById("serversTableBody");
const selectedServerText = document.getElementById("selectedServerText");
const selectedHostOperationText = document.getElementById("selectedHostOperationText");
const loadContainersBtn = document.getElementById("loadContainersBtn");
const loadImagesBtn = document.getElementById("loadImagesBtn");
const containersTableBody = document.getElementById("containersTableBody");
const imagesTableBody = document.getElementById("imagesTableBody");
const logsOutput = document.getElementById("logsOutput");
const tailInput = document.getElementById("tailInput");
const refreshTasksBtn = document.getElementById("refreshTasksBtn");
const recentTasksTableBody = document.getElementById("recentTasksTableBody");
const artifactUploadForm = document.getElementById("artifactUploadForm");
const artifactFileInput = document.getElementById("artifactFileInput");
const artifactKindSelect = document.getElementById("artifactKindSelect");
const refreshArtifactsBtn = document.getElementById("refreshArtifactsBtn");
const artifactsTableBody = document.getElementById("artifactsTableBody");
const exportImageForm = document.getElementById("exportImageForm");
const exportImageRefInput = document.getElementById("exportImageRefInput");
const exportArtifactNameInput = document.getElementById("exportArtifactNameInput");
const composeProjectInput = document.getElementById("composeProjectInput");
const composeFileInput = document.getElementById("composeFileInput");
const composeWorkdirInput = document.getElementById("composeWorkdirInput");

const storageKey = "host-agent-console-api-base";
const selectedServerStorageKey = "host-agent-console-selected-server";
const containerActionLabels = {
  start: "启动",
  stop: "停止",
  restart: "重启",
};

let selectedServerId = null;
let selectedServerName = "";

function inferDefaultApiBase() {
  const host = window.location.hostname || "127.0.0.1";
  const port = window.location.port || "14173";
  if (port === "14173") return `http://${host}:18000/api`;
  if (port === "4174") return `http://${host}:8010/api`;
  if (port === "4173") return `http://${host}:8000/api`;
  return `http://${host}:18000/api`;
}

function getApiBase() {
  return apiBaseInput.value.trim().replace(/\/$/, "");
}

function buildApiUrl(path) {
  return `${getApiBase()}${path}`;
}

function buildDownloadUrl(artifactId) {
  return buildApiUrl(`/artifacts/${artifactId}/download`);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDate(value) {
  if (!value) return "-";

  let normalized = value;
  if (
    typeof value === "string" &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value) &&
    !/(Z|[+-]\d{2}:\d{2})$/.test(value)
  ) {
    normalized = `${value}Z`;
  }

  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (!Number.isFinite(size) || size <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let current = size;
  let index = 0;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  return `${current.toFixed(current >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function translateStatus(status) {
  switch (status) {
    case "online":
      return "在线";
    case "offline":
      return "离线";
    case "pending":
      return "待执行";
    case "running":
      return "执行中";
    case "success":
      return "成功";
    case "failed":
      return "失败";
    default:
      return status || "-";
  }
}

function statusBadgeClass(status) {
  switch (status) {
    case "online":
    case "success":
      return "success";
    case "offline":
    case "failed":
      return "danger";
    default:
      return "";
  }
}

function setStatus(message, type = "info") {
  statusText.textContent = message;
  statusText.style.color =
    type === "error" ? "#dc2626" : type === "success" ? "#16a34a" : type === "warning" ? "#d97706" : "#0f172a";
}

async function parseResponse(response) {
  const raw = await response.text();
  let data = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = raw;
  }

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || `请求失败：${response.status}`);
  }

  return data;
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (typeof options.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers,
  });

  return parseResponse(response);
}

function updateSelectedServerUI() {
  if (!selectedServerId) {
    selectedServerText.textContent = "尚未选择宿主机";
    selectedHostOperationText.textContent = "未选择";
    return;
  }

  const displayName = selectedServerName || `宿主机 #${selectedServerId}`;
  selectedServerText.textContent = `已选择：${displayName} (ID: ${selectedServerId})`;
  selectedHostOperationText.textContent = `${displayName} (ID: ${selectedServerId})`;
}

function persistSelectedServer() {
  if (!selectedServerId) {
    localStorage.removeItem(selectedServerStorageKey);
    return;
  }

  localStorage.setItem(
    selectedServerStorageKey,
    JSON.stringify({
      id: selectedServerId,
      name: selectedServerName,
    }),
  );
}

function restoreSelectedServer() {
  try {
    const raw = localStorage.getItem(selectedServerStorageKey);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    const serverId = Number(parsed?.id);
    if (!Number.isFinite(serverId) || serverId <= 0) return;
    selectedServerId = serverId;
    selectedServerName = String(parsed?.name || "");
  } catch {
    localStorage.removeItem(selectedServerStorageKey);
  }
}

function clearSelectedServer(options = {}) {
  const { keepStatus = false } = options;
  selectedServerId = null;
  selectedServerName = "";
  persistSelectedServer();
  updateSelectedServerUI();
  containersTableBody.innerHTML = '<tr><td colspan="6" class="empty">请先选择宿主机并加载容器</td></tr>';
  logsOutput.textContent = "等待加载日志...";
  if (!keepStatus) {
    setStatus("已清除当前宿主机选择", "warning");
  }
}

function syncSelectedServer(servers = []) {
  if (!selectedServerId) {
    updateSelectedServerUI();
    return;
  }

  const matchedServer = servers.find((server) => Number(server.id) === selectedServerId);
  if (!matchedServer) {
    clearSelectedServer({ keepStatus: true });
    setStatus("之前选择的宿主机已不存在，请重新选择。", "warning");
    return;
  }

  selectedServerName = matchedServer.name;
  persistSelectedServer();
  updateSelectedServerUI();
}

function ensureSelectedServer(actionLabel) {
  if (!selectedServerId) {
    setStatus(`请先选择宿主机，再执行${actionLabel}`, "error");
    return false;
  }
  return true;
}

function renderOverview(data) {
  const cards = [
    {
      label: "Web Portal",
      value: "已连接",
      note: "当前浏览器页面负责可视化与任务入口。",
    },
    {
      label: "API Server",
      value: data?.api_prefix || "-",
      note: "负责统一接入、任务编排、元数据与审计。",
    },
    {
      label: "Host Agent",
      value: `${data?.online_servers ?? 0} / ${data?.total_servers ?? 0}`,
      note: `在线 Agent / 总宿主机，心跳超时 ${data?.heartbeat_timeout_seconds ?? "-"} 秒。`,
    },
    {
      label: "DB / Tasks",
      value: `${data?.pending_tasks ?? 0} 待执行`,
      note: `运行中 ${data?.running_tasks ?? 0}，累计 ${data?.total_tasks ?? 0} 个任务。`,
    },
    {
      label: "Artifact Store",
      value: `${data?.total_artifacts ?? 0}`,
      note: "镜像包、Compose 包等制品统一归档。",
    },
    {
      label: "Agent 能力",
      value: `${data?.capabilities?.length ?? 0}`,
      note: (data?.capabilities || []).join("、") || "等待 Agent 注册上报能力。",
    },
  ];

  overviewCards.innerHTML = cards
    .map(
      (card) => `
        <article class="overview-card">
          <span class="card-label">${escapeHtml(card.label)}</span>
          <strong class="card-value">${escapeHtml(card.value)}</strong>
          <span class="card-note">${escapeHtml(card.note)}</span>
        </article>
      `,
    )
    .join("");
}

function renderCapabilities(capabilities = []) {
  if (!capabilities.length) return '<span class="muted">-</span>';
  return `<div class="badge-list">${capabilities
    .map((item) => `<span class="badge">${escapeHtml(item)}</span>`)
    .join("")}</div>`;
}

function renderServers(servers) {
  if (!servers.length) {
    serversTableBody.innerHTML = '<tr><td colspan="8" class="empty">暂无宿主机</td></tr>';
    return;
  }

  serversTableBody.innerHTML = servers
    .map((server) => {
      const isSelected = Number(server.id) === selectedServerId;
      return `
        <tr class="${isSelected ? "is-selected" : ""}" data-server-id="${server.id}">
          <td>${server.id}</td>
          <td>${escapeHtml(server.name)}</td>
          <td>${escapeHtml(server.host || "-")}</td>
          <td>${escapeHtml(server.agent_id)}</td>
          <td>${renderCapabilities(server.capabilities)}</td>
          <td><span class="badge ${statusBadgeClass(server.status)}">${translateStatus(server.status)}</span></td>
          <td>${formatDate(server.last_seen_at)}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-primary" data-action="select-server" data-id="${server.id}" data-name="${escapeHtml(server.name)}">选择</button>
              <button class="btn" data-action="test-connection" data-id="${server.id}" data-name="${escapeHtml(server.name)}">检查 Agent</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderContainers(containers) {
  if (!containers.length) {
    containersTableBody.innerHTML = '<tr><td colspan="6" class="empty">当前宿主机暂无容器</td></tr>';
    return;
  }

  containersTableBody.innerHTML = containers
    .map(
      (container) => `
        <tr>
          <td>${escapeHtml(container.name)}</td>
          <td>${escapeHtml(container.image)}</td>
          <td>${escapeHtml(container.status || "-")}</td>
          <td>${escapeHtml(container.ports || "-")}</td>
          <td>${escapeHtml(container.running_for || "-")}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-success" data-action="start-container" data-name="${escapeHtml(container.name)}">启动</button>
              <button class="btn btn-danger" data-action="stop-container" data-name="${escapeHtml(container.name)}">停止</button>
              <button class="btn" data-action="restart-container" data-name="${escapeHtml(container.name)}">重启</button>
              <button class="btn" data-action="view-logs" data-name="${escapeHtml(container.name)}">日志</button>
            </div>
          </td>
        </tr>
      `,
    )
    .join("");
}

function renderImages(images) {
  if (!images.length) {
    imagesTableBody.innerHTML = '<tr><td colspan="7" class="empty">当前宿主机暂无镜像</td></tr>';
    return;
  }

  imagesTableBody.innerHTML = images
    .map(
      (image) => `
        <tr>
          <td>${escapeHtml(image.repository || "<none>")}</td>
          <td>${escapeHtml(image.tag || "<none>")}</td>
          <td>${escapeHtml(image.id || "-")}</td>
          <td>${escapeHtml(image.digest || "-")}</td>
          <td>${escapeHtml(image.created_since || image.created_at || "-")}</td>
          <td>${escapeHtml(image.size || "-")}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-primary" data-action="export-image" data-reference="${escapeHtml(image.reference)}">导出</button>
              <button class="btn" data-action="fill-export-image" data-reference="${escapeHtml(image.reference)}">填入导出表单</button>
            </div>
          </td>
        </tr>
      `,
    )
    .join("");
}


function taskSummary(task) {
  if (task?.result && typeof task.result === "object") {
    return task.result.message || task.result.output || task.result.logs || JSON.stringify(task.result);
  }
  return task?.error || "-";
}

function truncateText(value, maxLength = 160) {
  const text = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return "-";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}

function renderTasks(tasks) {
  if (!tasks.length) {
    recentTasksTableBody.innerHTML = '<tr><td colspan="7" class="empty">暂无任务</td></tr>';
    return;
  }

  recentTasksTableBody.innerHTML = tasks
    .map(
      (task) => `
        <tr>
          <td>${task.id}</td>
          <td>${escapeHtml(task.server_name)}</td>
          <td>${escapeHtml(task.task_type)}</td>
          <td><span class="badge ${statusBadgeClass(task.status)}">${translateStatus(task.status)}</span></td>
          <td>${formatDate(task.created_at)}</td>
          <td>${formatDate(task.finished_at)}</td>
          <td class="summary-cell" title="${escapeHtml(taskSummary(task))}">${escapeHtml(truncateText(taskSummary(task)))}</td>
        </tr>
      `,
    )
    .join("");
}

function renderArtifacts(artifacts) {
  if (!artifacts.length) {
    artifactsTableBody.innerHTML = '<tr><td colspan="7" class="empty">暂无制品</td></tr>';
    return;
  }

  artifactsTableBody.innerHTML = artifacts
    .map((artifact) => {
      let actionButtons = `
        <a class="btn" href="${buildDownloadUrl(artifact.id)}" target="_blank" rel="noopener noreferrer">下载</a>
      `;
      if (artifact.kind === "docker-image") {
        actionButtons += `<button class="btn btn-primary" data-action="import-image" data-id="${artifact.id}" data-name="${escapeHtml(artifact.file_name)}">导入到当前主机</button>`;
      }
      if (artifact.kind === "compose-bundle") {
        actionButtons += `<button class="btn btn-warning" data-action="deploy-compose" data-id="${artifact.id}" data-name="${escapeHtml(artifact.file_name)}">部署到当前主机</button>`;
      }

      return `
        <tr>
          <td>${artifact.id}</td>
          <td>${escapeHtml(artifact.file_name)}</td>
          <td><span class="badge">${escapeHtml(artifact.kind)}</span></td>
          <td>${formatBytes(artifact.size_bytes)}</td>
          <td>${escapeHtml(artifact.source || "-")}</td>
          <td>${formatDate(artifact.created_at)}</td>
          <td><div class="row-actions">${actionButtons}</div></td>
        </tr>
      `;
    })
    .join("");
}

async function checkHealth() {
  try {
    const data = await request("/health", { method: "GET" });
    setStatus(`后端可用：${data.message}`, "success");
  } catch (error) {
    setStatus(`后端检查失败：${error.message}`, "error");
  }
}

async function loadOverview() {
  try {
    const data = await request("/system/overview", { method: "GET" });
    renderOverview(data);
  } catch (error) {
    renderOverview(null);
    setStatus(`系统总览加载失败：${error.message}`, "error");
  }
}

async function loadServers() {
  try {
    const servers = await request("/servers", { method: "GET" });
    syncSelectedServer(servers);
    renderServers(servers);
  } catch (error) {
    renderServers([]);
    updateSelectedServerUI();
    setStatus(`宿主机加载失败：${error.message}`, "error");
  }
}

async function loadTasks() {
  try {
    const tasks = await request("/tasks?limit=20", { method: "GET" });
    renderTasks(tasks);
  } catch (error) {
    renderTasks([]);
    setStatus(`任务加载失败：${error.message}`, "error");
  }
}

async function loadArtifacts() {
  try {
    const artifacts = await request("/artifacts", { method: "GET" });
    renderArtifacts(artifacts);
  } catch (error) {
    renderArtifacts([]);
    setStatus(`制品加载失败：${error.message}`, "error");
  }
}

async function createServer(event) {
  event.preventDefault();

  const formData = new FormData(serverForm);
  const payload = {
    name: formData.get("name")?.toString().trim(),
    agent_id: formData.get("agent_id")?.toString().trim(),
    host: formData.get("host")?.toString().trim() || null,
    description: formData.get("description")?.toString().trim() || null,
    tags: (formData.get("tags")?.toString() || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  };

  try {
    setStatus(`正在创建宿主机 ${payload.name} ...`);
    await request("/servers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    serverForm.reset();
    setStatus(`宿主机 ${payload.name} 创建成功`, "success");
    await Promise.all([loadServers(), loadOverview()]);
  } catch (error) {
    setStatus(`宿主机创建失败：${error.message}`, "error");
  }
}

async function pingServer(serverId, serverName) {
  try {
    setStatus(`正在 Ping ${serverName} ...`);
    const data = await request(`/servers/${serverId}/ping`, { method: "POST" });
    setStatus(`${serverName}：${data.message}`, data.success ? "success" : "warning");
  } catch (error) {
    setStatus(`Ping 检测失败：${error.message}`, "error");
  }
}

async function testConnection(serverId, serverName) {
  try {
    setStatus(`正在检查 ${serverName} 的 Host Agent ...`);
    const data = await request(`/servers/${serverId}/test-connection`, { method: "POST" });
    setStatus(`${serverName}：${data.message}`, data.success ? "success" : "warning");
    await Promise.all([loadServers(), loadOverview()]);
  } catch (error) {
    setStatus(`Agent 检查失败：${error.message}`, "error");
  }
}

function refreshServerSelectionHighlight() {
  serversTableBody.querySelectorAll("tr[data-server-id]").forEach((row) => {
    row.classList.toggle("is-selected", Number(row.dataset.serverId) === selectedServerId);
  });
}

function selectServer(serverId, serverName) {
  selectedServerId = Number(serverId);
  selectedServerName = serverName || `\u5bbf\u4e3b\u673a #${serverId}`;
  persistSelectedServer();
  updateSelectedServerUI();
  refreshServerSelectionHighlight();
  containersTableBody.innerHTML = '<tr><td colspan="6" class="empty">\u5df2\u9009\u62e9\u5bbf\u4e3b\u673a\uff0c\u8bf7\u70b9\u51fb\u201c\u52a0\u8f7d\u5bb9\u5668\u201d</td></tr>';
  imagesTableBody.innerHTML = '<tr><td colspan="7" class="empty">\u5df2\u9009\u62e9\u5bbf\u4e3b\u673a\uff0c\u8bf7\u70b9\u51fb\u201c\u52a0\u8f7d\u955c\u50cf\u201d</td></tr>';
  logsOutput.textContent = `\u5f53\u524d\u5bbf\u4e3b\u673a\uff1a${selectedServerName}\n\u7b49\u5f85\u52a0\u8f7d\u5bb9\u5668\u65e5\u5fd7...`;
  setStatus(`\u5df2\u9009\u62e9\u5bbf\u4e3b\u673a\uff1a${selectedServerName}`, "success");
  setStatus(`已选择宿主机：${selectedServerName}`, "success");
}

async function loadContainers({ refreshTasks = true } = {}) {
  if (!ensureSelectedServer("加载容器")) return;
  try {
    setStatus(`正在从 ${selectedServerName} 加载容器 ...`);
    const containers = await request(`/servers/${selectedServerId}/containers`, { method: "GET" });
    renderContainers(containers);
    setStatus(`已加载 ${containers.length} 个容器`, "success");
  } catch (error) {
    renderContainers([]);
    setStatus(`容器加载失败：${error.message}`, "error");
  } finally {
    if (refreshTasks) await loadTasks();
  }
}

async function loadImages({ refreshTasks = true } = {}) {
  if (!ensureSelectedServer("加载镜像")) return;
  try {
    setStatus(`正在从 ${selectedServerName} 加载镜像 ...`);
    const images = await request(`/servers/${selectedServerId}/images`, { method: "GET", timeoutMs: 120000 });
    renderImages(images);
    setStatus(`已加载 ${images.length} 个镜像`, "success");
  } catch (error) {
    renderImages([]);
    setStatus(`镜像加载失败：${error.message}`, "error");
  } finally {
    if (refreshTasks) await loadTasks();
  }
}

async function containerAction(action, containerName) {
  const actionLabel = containerActionLabels[action] || action;
  if (!ensureSelectedServer(`容器${actionLabel}`)) return;
  try {
    setStatus(`正在执行${actionLabel}：${containerName} ...`);
    const result = await request(`/servers/${selectedServerId}/containers/${encodeURIComponent(containerName)}/${action}`, { method: "POST" });
    setStatus(result.message || `${containerName} ${actionLabel}完成`, "success");
    await Promise.all([loadContainers({ refreshTasks: false }), loadTasks(), loadOverview()]);
  } catch (error) {
    setStatus(`容器操作失败：${error.message}`, "error");
    await loadTasks();
  }
}

async function loadLogs(containerName, { refreshTasks = true } = {}) {
  if (!ensureSelectedServer("查看日志")) return;
  try {
    const tail = Math.max(1, Math.min(2000, Number(tailInput.value || 200) || 200));
    tailInput.value = String(tail);
    setStatus(`正在加载 ${containerName} 的日志 ...`);
    const result = await request(`/servers/${selectedServerId}/containers/${encodeURIComponent(containerName)}/logs?tail=${tail}`, { method: "GET" });
    logsOutput.textContent = result.logs || "暂无日志";
    setStatus(`日志加载成功：${containerName}`, "success");
  } catch (error) {
    logsOutput.textContent = `日志加载失败：${error.message}`;
    setStatus(`日志加载失败：${error.message}`, "error");
  } finally {
    if (refreshTasks) await loadTasks();
  }
}

async function uploadArtifact(event) {
  event.preventDefault();
  const file = artifactFileInput.files?.[0];
  if (!file) {
    setStatus("请先选择需要上传的文件", "error");
    return;
  }
  try {
    setStatus(`正在上传制品 ${file.name} ...`);
    const response = await fetch(buildApiUrl("/artifacts/upload"), {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Artifact-Name": encodeURIComponent(file.name),
        "X-Artifact-Kind": encodeURIComponent(artifactKindSelect.value),
        "X-Artifact-Source": encodeURIComponent("web-portal"),
      },
      body: file,
    });
    const data = await parseResponse(response);
    artifactUploadForm.reset();
    setStatus(`制品上传成功：${data.file_name}`, "success");
    await Promise.all([loadArtifacts(), loadOverview()]);
  } catch (error) {
    setStatus(`制品上传失败：${error.message}`, "error");
  }
}

async function exportImageByReference(imageRef, artifactName = "") {
  if (!ensureSelectedServer("镜像导出")) return;
  const normalizedRef = String(imageRef || "").trim();
  const normalizedArtifactName = String(artifactName || "").trim();
  if (!normalizedRef) {
    setStatus("请输入要导出的镜像名称", "error");
    return;
  }
  try {
    setStatus(`正在导出镜像 ${normalizedRef} ...`);
    const data = await request(`/servers/${selectedServerId}/images/export`, {
      method: "POST",
      body: JSON.stringify({ image_ref: normalizedRef, artifact_name: normalizedArtifactName || null }),
    });
    setStatus(data.message || `镜像 ${normalizedRef} 导出完成`, "success");
    await Promise.all([loadTasks(), loadArtifacts(), loadOverview(), loadImages({ refreshTasks: false })]);
  } catch (error) {
    setStatus(`镜像导出失败：${error.message}`, "error");
    await loadTasks();
  }
}

async function exportImage(event) {
  event.preventDefault();
  const imageRef = exportImageRefInput.value.trim();
  const artifactName = exportArtifactNameInput.value.trim();
  await exportImageByReference(imageRef, artifactName);
  if (imageRef) exportImageForm.reset();
}

async function importArtifactImage(artifactId, artifactName) {
  if (!ensureSelectedServer("镜像导入")) return;
  try {
    setStatus(`正在向 ${selectedServerName} 导入镜像包 ${artifactName} ...`);
    const data = await request(`/servers/${selectedServerId}/images/import`, { method: "POST", body: JSON.stringify({ artifact_id: Number(artifactId) }) });
    setStatus(data.message || `镜像包 ${artifactName} 导入完成`, "success");
    await Promise.all([loadTasks(), loadOverview(), loadImages({ refreshTasks: false })]);
  } catch (error) {
    setStatus(`镜像导入失败：${error.message}`, "error");
    await loadTasks();
  }
}

async function deployComposeBundle(artifactId, artifactName) {
  if (!ensureSelectedServer("Compose 部署")) return;
  try {
    setStatus(`正在向 ${selectedServerName} 部署 Compose 包 ${artifactName} ...`);
    const data = await request(`/servers/${selectedServerId}/deployments/compose`, {
      method: "POST",
      body: JSON.stringify({
        artifact_id: Number(artifactId),
        project_name: composeProjectInput.value.trim() || null,
        compose_file: composeFileInput.value.trim() || "docker-compose.yml",
        workdir: composeWorkdirInput.value.trim() || null,
      }),
    });
    setStatus(data.message || `Compose 包 ${artifactName} 部署完成`, "success");
    await Promise.all([loadTasks(), loadOverview(), loadContainers({ refreshTasks: false })]);
  } catch (error) {
    setStatus(`Compose 部署失败：${error.message}`, "error");
    await loadTasks();
  }
}

serversTableBody.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const serverId = target.dataset.id;
  const serverName = target.dataset.name;
  if (action === "select-server") selectServer(serverId, serverName);
  if (action === "ping-server") pingServer(serverId, serverName);
  if (action === "test-connection") testConnection(serverId, serverName);
});

containersTableBody.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const containerName = target.dataset.name;
  if (action === "start-container") containerAction("start", containerName);
  if (action === "stop-container") containerAction("stop", containerName);
  if (action === "restart-container") containerAction("restart", containerName);
  if (action === "view-logs") loadLogs(containerName);
});

artifactsTableBody.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const artifactId = target.dataset.id;
  const artifactName = target.dataset.name;
  if (action === "import-image") importArtifactImage(artifactId, artifactName);
  if (action === "deploy-compose") deployComposeBundle(artifactId, artifactName);
});

imagesTableBody.addEventListener("click", (event) => {
  const target = event.target.closest("button[data-action]");
  if (!target) return;
  const action = target.dataset.action;
  const imageReference = target.dataset.reference;
  if (action === "export-image") {
    exportImageRefInput.value = imageReference || "";
    exportImageByReference(imageReference || "");
  }
  if (action === "fill-export-image") {
    exportImageRefInput.value = imageReference || "";
    exportImageRefInput.focus();
    setStatus(`已将镜像 ${imageReference} 填入导出表单`, "success");
  }
});

saveApiBtn.addEventListener("click", () => {
  const apiBase = getApiBase();
  if (!apiBase) {
    setStatus("API 地址不能为空", "error");
    return;
  }
  localStorage.setItem(storageKey, apiBase);
  setStatus(`API 地址已保存：${apiBase}`, "success");
});

healthBtn.addEventListener("click", checkHealth);
refreshOverviewBtn.addEventListener("click", loadOverview);
serverForm.addEventListener("submit", createServer);
refreshServersBtn.addEventListener("click", loadServers);
loadContainersBtn.addEventListener("click", loadContainers);
loadImagesBtn.addEventListener("click", loadImages);
refreshTasksBtn.addEventListener("click", loadTasks);
artifactUploadForm.addEventListener("submit", uploadArtifact);
refreshArtifactsBtn.addEventListener("click", loadArtifacts);
exportImageForm.addEventListener("submit", exportImage);

(async function init() {
  const savedApiBase = localStorage.getItem(storageKey);
  apiBaseInput.value = savedApiBase || inferDefaultApiBase();
  restoreSelectedServer();
  updateSelectedServerUI();
  await checkHealth();
  await Promise.all([loadOverview(), loadServers(), loadTasks(), loadArtifacts()]);
  if (selectedServerId) {
    await loadImages({ refreshTasks: false });
  }
})();
