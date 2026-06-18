const dynamicPanel = document.getElementById('dynamicPanel');
const viewTitle = document.getElementById('viewTitle');
const versionBadge = document.getElementById('versionBadge');
const sidebar = document.getElementById('sidebar');

// [2026-06-16 07:20:19] 更新构建标识，清掉浏览器端本地资源导航旧缓存
const BUILD_TAG = '\u6784\u5efa 20260616-02';
const API_KEY = 'customer-portal-api-base';
const SERVER_KEY = 'customer-portal-selected-server';
const DEFAULT_REQUEST_TIMEOUT_MS = 120000;
const OFFLINE_PING_INTERVAL_MS = 60000;
// [2026-04-24 11:28:51] 根治服务器列表周期性“被刷新”体感：默认关闭离线探测轮询
const ENABLE_OFFLINE_PING_POLLING = false;
// [2026-04-24 10:45:36] 当前阶段默认关闭智能助手入口，仅保留其它视图联调
const ENABLE_AGENT_VIEW = false;

const state = {
    currentView: 'home',
    overview: {
        total_servers: 0,
        online_servers: 0,
        total_artifacts: 0,
        pending_tasks: 0,
        running_tasks: 0,
        success_tasks: 0,
    },
    servers: [],
    artifacts: [],
    tasks: [],
    dockerRows: [],
    dockerImages: [],
    dockerErrors: { containers: '', images: '' },
    chatMessages: [],
    isWaiting: false,
    selectedServerId: null,
    selectedServerName: '',
    lastError: '',
    pingStatusByServerId: {},
    offlinePingTimerId: null,
    serverDynamicTimerId: null,
    pingSweepRunning: false,
};

const viewMeta = {
    home: { title: '\u96c6\u7fa4\u603b\u89c8 \u00b7 \u667a\u80fd\u7f51\u7ba1', badge: '\u878d\u5408\u89c6\u56fe \u00b7 V1 + V2 + V3' },
    servers: { title: '\u7269\u7406\u670d\u52a1\u5668\u7ba1\u7406 \u00b7 \u8d44\u6e90\u76d1\u63a7', badge: 'V1 \u00b7 \u7269\u7406\u57fa\u7840\u8bbe\u65bd' },
    docker: { title: '\u5bb9\u5668\u4e0e\u955c\u50cf\u7ba1\u7406 \u00b7 Docker', badge: 'V2 \u00b7 \u5bb9\u5668\u8fd0\u884c\u65f6' },
    artifacts: { title: '交付件管理 \u00b7 \u4ea4\u4ed8\u6587\u4ef6\u7ba1\u7406', badge: '\u9644\u52a0\u6a21\u5757 \u00b7 \u4ea4\u4ed8\u4ef6\u4e0e\u90e8\u7f72\u5305' },
    'local-images': { title: '本地镜像库 \u00b7 \u955c\u50cf\u8d44\u4ea7', badge: '\u9644\u52a0\u6a21\u5757 \u00b7 Docker Image Archive' },
    'local-resources': { title: '本地资源导航 \u00b7 \u5e73\u53f0\u5165\u53e3', badge: '\u4fbf\u6377\u5165\u53e3 \u00b7 \u5c40\u57df\u7f51\u8d44\u6e90' },
    agent: { title: '\u667a\u80fd\u8fd0\u7ef4\u52a9\u624b', badge: '\u667a\u80fd\u8fd0\u7ef4\u52a9\u624b' },
};

function inferDefaultApiBase() {
    const host = window.location.hostname || '127.0.0.1';
    const port = window.location.port || '14173';
    if (port === '14173') return `http://${host}:18000/api`;
    if (port === '4174') return `http://${host}:8010/api`;
    if (port === '4173') return `http://${host}:8000/api`;
    return `http://${host}:18000/api`;
}

function normalizeApiBase(value) {
    return String(value || '').trim().replace(/\/$/, '');
}

function getApiBase() {
    const inferred = normalizeApiBase(inferDefaultApiBase());
    try {
        const stored = normalizeApiBase(localStorage.getItem(API_KEY));
        // [2026-05-21 01:55:19] 合法的手动 API 配置优先，不再因 host 不同被自动推断值覆盖
        if (stored) {
            new URL(stored);
            return stored;
        }
        localStorage.setItem(API_KEY, inferred);
    } catch {
        try { localStorage.setItem(API_KEY, inferred); } catch {}
    }
    return inferred;
}

function api(path) {
    return `${getApiBase()}${path}`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(value) {
    if (!value) return '-';
    let normalized = value;
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value) && !/(Z|[+-]\d{2}:\d{2})$/.test(value)) {
        normalized = `${value}Z`;
    }
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return date.toLocaleString('zh-CN', { hour12: false });
}

function formatBytes(value) {
    const size = Number(value || 0);
    if (!Number.isFinite(size) || size <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let current = size;
    let index = 0;
    while (current >= 1024 && index < units.length - 1) {
        current /= 1024;
        index += 1;
    }
    return `${current.toFixed(current >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function toFiniteNumber(candidate) {
    if (typeof candidate === 'number' && Number.isFinite(candidate)) return candidate;
    if (typeof candidate === 'string') {
        const normalized = candidate.trim().replace(/,/g, '').replace(/%$/, '');
        if (!normalized) return null;
        const parsed = Number(normalized);
        if (Number.isFinite(parsed)) return parsed;
    }
    const direct = Number(candidate);
    return Number.isFinite(direct) ? direct : null;
}

function firstFiniteNumber(...candidates) {
    for (const candidate of candidates) {
        const num = toFiniteNumber(candidate);
        if (Number.isFinite(num)) return num;
    }
    return null;
}

function clampPercent(value) {
    if (!Number.isFinite(value)) return null;
    return Math.max(0, Math.min(100, value));
}

function deriveMemoryPercent(totalBytes, usedBytes) {
    const total = firstFiniteNumber(totalBytes);
    const used = firstFiniteNumber(usedBytes);
    if (total === null || used === null || total <= 0) return null;
    return clampPercent((used / total) * 100);
}

function formatPercent(value) {
    if (!Number.isFinite(value)) return '--';
    return `${Math.round(clampPercent(value) || 0)}%`;
}

function statusText(status) {
    return {
        online: '\u5728\u7ebf',
        offline: '\u79bb\u7ebf',
        running: '\u8fd0\u884c\u4e2d',
        exited: '\u5df2\u505c\u6b62',
        success: '\u6210\u529f',
        failed: '\u5931\u8d25',
        pending: '\u5f85\u5904\u7406',
        created: '\u5df2\u521b\u5efa',
    }[status] || status || '-';
}

function showErrorBanner() {
    if (!state.lastError) return '';
    return `<div class="api-error-banner">\u63a5\u53e3\u52a0\u8f7d\u5931\u8d25\uff1a${escapeHtml(state.lastError)}</div>`;
}

function showInlineBanner(message, type = 'error') {
    if (!message) return '';
    const cls = type === 'info' ? 'info-banner' : 'api-error-banner';
    return `<div class="${cls}">${escapeHtml(message)}</div>`;
}

// [2026-04-24 10:45:36] 统一使用页面内轻提示，替代阻塞式 alert
function showToast(message, type = 'info') {
    const text = String(message || '').trim();
    if (!text) return;
    const id = 'portalToastContainer';
    let container = document.getElementById(id);
    if (!container) {
        container = document.createElement('div');
        container.id = id;
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const item = document.createElement('div');
    item.className = `toast toast-${type}`;
    item.textContent = text;
    container.appendChild(item);
    window.setTimeout(() => item.classList.add('show'), 10);
    window.setTimeout(() => {
        item.classList.remove('show');
        window.setTimeout(() => item.remove(), 180);
    }, 2800);
}

function refreshApiBaseLabel() {
    const label = document.getElementById('apiBaseLabel');
    if (!label) return;
    label.textContent = getApiBase();
    label.title = getApiBase();
}
async function parseResponse(resp) {
    const raw = await resp.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : null;
    } catch {
        data = raw;
    }
    if (!resp.ok) {
        throw new Error(data?.detail || data?.message || `\u8bf7\u6c42\u5931\u8d25\uff1a${resp.status}`);
    }
    return data;
}

async function request(path, options = {}) {
    const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...fetchOptions } = options;
    const headers = new Headers(fetchOptions.headers || {});
    if (typeof fetchOptions.body === 'string' && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
    }
    let timeoutId = 0;
    const timeoutSeconds = Math.max(1, Math.round(timeoutMs / 1000));
    const timeoutPromise = new Promise((_, reject) => {
        timeoutId = window.setTimeout(() => reject(new Error(`\u8bf7\u6c42\u8d85\u65f6\uff08>${timeoutSeconds}s\uff09\uff0c\u8bf7\u68c0\u67e5 API \u670d\u52a1\u72b6\u6001\u6216\u7f51\u7edc\u8fde\u901a\u6027`)), timeoutMs);
    });
    try {
        const resp = await Promise.race([fetch(api(path), { ...fetchOptions, headers }), timeoutPromise]);
        return await parseResponse(resp);
    } catch (error) {
        const message = String(error?.message || '');
        if (/signal is aborted without reason/i.test(message)) {
            throw new Error('\u6d4f\u89c8\u5668\u4e2d\u65ad\u4e86\u5f53\u524d\u8bf7\u6c42\uff0c\u8bf7\u5237\u65b0\u9875\u9762\u540e\u91cd\u8bd5\u3002');
        }
        if (error instanceof TypeError) {
            throw new Error(`\u65e0\u6cd5\u8fde\u63a5 API\uff1a${getApiBase()}`);
        }
        throw error;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function saveSelectedServer() {
    if (!state.selectedServerId) {
        localStorage.removeItem(SERVER_KEY);
        return;
    }
    localStorage.setItem(SERVER_KEY, JSON.stringify({ id: state.selectedServerId, name: state.selectedServerName }));
}

function restoreSelectedServer() {
    try {
        const raw = localStorage.getItem(SERVER_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        state.selectedServerId = Number(parsed.id);
        state.selectedServerName = parsed.name || '';
    } catch {
        localStorage.removeItem(SERVER_KEY);
    }
}

async function saveOwnerUser(serverId, value) {
    const normalized = String(value || '').trim();
    await request(`/servers/${serverId}`, {
        method: 'PUT',
        body: JSON.stringify({ owner_user: normalized || null }),
    });
}

function getOwnerUser(server) {
    return String(server.ownerUser || '').trim();
}

// [2026-04-24 10:58:02] 使用人按常见分隔符拆分，支持 UI 中逐个追加
function parseOwnerUsers(value) {
    return String(value || '')
        .split(/[，,、;；\n]/)
        .map((item) => item.trim())
        .filter(Boolean);
}

function joinOwnerUsers(users) {
    return Array.from(new Set((users || []).map((item) => String(item || '').trim()).filter(Boolean))).join(', ');
}

// [2026-04-24 14:24:20] 容器列表使用人展示：复用服务器 owner_user 并标签化只读呈现
function ownerTagsReadonlyHtml(serverId) {
    const matched = state.servers.find((item) => Number(item.id) === Number(serverId));
    const owners = parseOwnerUsers(matched?.ownerUser || '');
    if (!owners.length) return '<span class="metric-subtext">-</span>';
    return `<div class="owner-tags owner-tags-readonly">${owners.map((name) => `<span class="owner-chip">${escapeHtml(name)}</span>`).join('')}</div>`;
}

function chooseServer(serverId) {
    const matched = state.servers.find((item) => Number(item.id) === Number(serverId));
    if (!matched) return false;
    // [2026-04-24 11:36:58] 已选中同一服务器时不重复触发后续重绘链路
    if (Number(state.selectedServerId) === Number(matched.id)) return false;
    state.selectedServerId = Number(matched.id);
    state.selectedServerName = matched.name;
    saveSelectedServer();
    return true;
}

function ensureSelectedServer() {
    if (!state.selectedServerId && state.servers.length) chooseServer(state.servers[0].id);
}

async function loadOverview() {
    state.overview = await request('/system/overview');
}

async function loadServers() {
    const rows = await request('/servers');
    state.servers = rows.map((server) => {
        const memoryTotalBytes = firstFiniteNumber(server.memory_total_bytes, server.mem_total_bytes);
        const memoryUsedBytes = firstFiniteNumber(server.memory_used_bytes, server.mem_used_bytes);
        const cpu = clampPercent(firstFiniteNumber(server.cpu_percent, server.cpu_usage, server.cpu));
        const mem = clampPercent(firstFiniteNumber(server.memory_percent, server.mem_percent, server.memory_usage_percent, deriveMemoryPercent(memoryTotalBytes, memoryUsedBytes)));
        return {
            id: server.id,
            name: server.name,
            ip: server.management_ip || server.host || '-',
            hostIp: server.host_ip || server.host || '-',
            status: server.status,
            cpu,
            mem,
            memoryTotalBytes,
            memoryUsedBytes,
            location: server.description || (server.tags?.[0] || '-'),
            reportedUser: server.owner_user || server.reported_user || '-',
            ownerUser: server.owner_user || '',
            osName: server.os_name || '-',
            runtime: server.runtime || server.agent_version || '-',
            lastSeenAt: server.last_seen_at,
        };
    });
    if (state.selectedServerId && !state.servers.find((item) => Number(item.id) === state.selectedServerId)) {
        state.selectedServerId = null;
        state.selectedServerName = '';
    }
    cleanupPingStateCache();
    ensureSelectedServer();
}

async function loadArtifacts() {
    state.artifacts = await request('/artifacts');
}

async function loadTasks() {
    state.tasks = await request('/tasks?limit=20');
}

async function loadDockerContainers() {
    if (!state.selectedServerId) {
        state.dockerRows = [];
        return;
    }
    const containers = await request(`/servers/${state.selectedServerId}/containers`, { timeoutMs: 120000 });
    state.dockerRows = containers.map((container) => ({
        serverId: state.selectedServerId,
        server: state.selectedServerName,
        imageName: container.image,
        containerName: container.name,
        status: container.state || container.status || '-',
        ports: container.ports || '-',
        runningFor: container.running_for || '-',
    }));
}

async function loadDockerImages() {
    if (!state.selectedServerId) {
        state.dockerImages = [];
        return;
    }
    const images = await request(`/servers/${state.selectedServerId}/images`, { timeoutMs: 120000 });
    state.dockerImages = images.map((image) => ({
        repository: image.repository || '<none>',
        tag: image.tag || '<none>',
        id: image.id || '-',
        reference: image.reference || (image.repository && image.tag ? `${image.repository}:${image.tag}` : image.id || ''),
        digest: image.digest || '-',
        createdAt: image.created_since || image.created_at || '-',
        size: image.size || '-',
    }));
}

async function loadDockerResources() {
    if (!state.selectedServerId) {
        state.dockerRows = [];
        state.dockerImages = [];
        state.dockerErrors = { containers: '', images: '' };
        return;
    }

    state.dockerErrors = { containers: '', images: '' };

    try {
        await loadDockerContainers();
    } catch (error) {
        state.dockerRows = [];
        state.dockerErrors.containers = error?.message || '\u5bb9\u5668\u5217\u8868\u52a0\u8f7d\u5931\u8d25';
    }

    try {
        await loadDockerImages();
    } catch (error) {
        state.dockerImages = [];
        state.dockerErrors.images = error?.message || '\u955c\u50cf\u5217\u8868\u52a0\u8f7d\u5931\u8d25';
    }
}
function setHeader(view) {
    const meta = viewMeta[view] || viewMeta.home;
    viewTitle.innerText = meta.title;
    versionBadge.innerText = `${meta.badge} \u00b7 ${BUILD_TAG}`;
}

function pingCacheKey(serverId) {
    return String(serverId);
}

function getPingStatus(serverId) {
    return state.pingStatusByServerId[pingCacheKey(serverId)] || null;
}

function setPingStatus(serverId, payload) {
    const key = pingCacheKey(serverId);
    state.pingStatusByServerId[key] = { ...(state.pingStatusByServerId[key] || {}), ...payload };
}

// [2026-04-24 11:16:57] 仅比较影响展示的核心字段，避免时间戳变化触发无意义重绘
function isPingUiChanged(before, after) {
    const prev = before || {};
    const next = after || {};
    return (
        String(prev.state || '') !== String(next.state || '') ||
        String(prev.message || '') !== String(next.message || '') ||
        String(prev.latencyMs ?? '') !== String(next.latencyMs ?? '')
    );
}

function cleanupPingStateCache() {
    const validIds = new Set(state.servers.map((item) => pingCacheKey(item.id)));
    Object.keys(state.pingStatusByServerId).forEach((key) => {
        const server = state.servers.find((item) => pingCacheKey(item.id) === key);
        if (!validIds.has(key) || (server && server.status === 'online')) {
            delete state.pingStatusByServerId[key];
        }
    });
}

function stopOfflinePingLoop() {
    if (state.offlinePingTimerId) {
        window.clearInterval(state.offlinePingTimerId);
        state.offlinePingTimerId = null;
    }
}

async function pingOfflineServers(options = {}) {
    // [2026-04-24 11:18:31] 深度优化：离线探测只更新徽标，不触发整列表重绘
    const { renderAfterEach = false } = options;
    if (state.pingSweepRunning) return;

    const offlineServers = state.servers.filter((item) => item.status !== 'online');
    if (!offlineServers.length) {
        cleanupPingStateCache();
        return;
    }

    state.pingSweepRunning = true;

    for (const server of offlineServers) {
        const before = getPingStatus(server.id);
        try {
            const data = await request(`/servers/${server.id}/ping`, { method: 'POST', timeoutMs: 10000 });
            setPingStatus(server.id, {
                state: data.success ? 'success' : 'failed',
                message: data.message || '',
                checkedAt: data.checked_at || new Date().toISOString(),
                latencyMs: data.latency_ms ?? null,
            });
        } catch (error) {
            setPingStatus(server.id, {
                state: 'failed',
                message: error?.message || '\u0050\u0069\u006e\u0067 \u68c0\u6d4b\u5931\u8d25',
                checkedAt: new Date().toISOString(),
                latencyMs: null,
            });
        }

        const after = getPingStatus(server.id);
        if (isPingUiChanged(before, after)) {
            updateServerNetworkBadgeInPlace(server.id);
        }
        if (state.currentView === 'servers' && renderAfterEach) {
            updateServerNetworkBadgeInPlace(server.id);
        }
    }

    state.pingSweepRunning = false;
}

function startOfflinePingLoop() {
    stopOfflinePingLoop();
    if (state.currentView !== 'servers') return;
    // [2026-04-24 11:28:51] 仅在进入页面时探测一次，避免 setInterval 持续触发局部更新
    pingOfflineServers({ renderAfterEach: false });
    if (!ENABLE_OFFLINE_PING_POLLING) return;
    state.offlinePingTimerId = window.setInterval(() => {
        pingOfflineServers({ renderAfterEach: false });
    }, OFFLINE_PING_INTERVAL_MS);
}

function sanitizeDockerErrorMessage(message) {
    const text = String(message || '').trim();
    if (!text) return '';
    if (text.includes('\u0048\u006f\u0073\u0074\u0020\u0041\u0067\u0065\u006e\u0074\u0020\u5f53\u524d\u79bb\u7ebf\uff0c\u65e0\u6cd5\u4e0b\u53d1\u4efb\u52a1')) return '';
    return text;
}

function dockerServerOptionsHtml() {
    return state.servers.map((server) => {
        const selected = Number(server.id) === Number(state.selectedServerId) ? 'selected' : '';
        const suffix = server.status === 'online' ? '\u5728\u7ebf' : '\u79bb\u7ebf';
        return `<option value="${server.id}" ${selected}>${escapeHtml(server.name)} (${escapeHtml(suffix)})</option>`;
    }).join('');
}

function networkStatusBadgeHtml(server) {
    // [2026-04-24 14:13:58] 网络状态改为红绿灯图标 + 文案，增强一眼识别
    if (server.status === 'online') {
        return '<span class="status-badge status-online"><span class="status-dot status-dot-green"></span> 网络正常 - <span class="status-dot status-dot-green"></span> 在线</span>';
    }

    const ping = getPingStatus(server.id);
    if (ping?.state === 'success') {
        return '<span class="status-badge status-pending"><span class="status-dot status-dot-green"></span> 网络正常 - <span class="status-dot status-dot-yellow"></span> 未接入agent</span>';
    }
    if (ping?.state === 'failed') {
        return '<span class="status-badge status-offline"><span class="status-dot status-dot-red"></span> 网络异常 - <span class="status-dot status-dot-red"></span> 离线</span>';
    }
    return '<span class="status-badge status-pending"><span class="status-dot status-dot-red"></span> 网络检测中</span>';
}

// [2026-04-24 11:18:31] 仅更新网络状态徽标，避免服务器列表整卡片重绘
function updateServerNetworkBadgeInPlace(serverId) {
    if (state.currentView !== 'servers') return;
    const card = dynamicPanel.querySelector(`[data-server-card-id="${serverId}"]`);
    if (!card) return;
    const server = state.servers.find((item) => Number(item.id) === Number(serverId));
    if (!server) return;
    const badgeWrap = card.querySelector('.status-group [data-role="network-badge"]');
    if (!badgeWrap) return;
    badgeWrap.innerHTML = networkStatusBadgeHtml(server);
}

// [2026-04-24 11:41:37] 仅局部刷新动态指标（状态/CPU/内存），避免静态信息重绘
function updateServerDynamicMetricsInPlace(serverId) {
    if (state.currentView !== 'servers') return;
    const card = dynamicPanel.querySelector(`[data-server-card-id="${serverId}"]`);
    if (!card) return;
    const server = state.servers.find((item) => Number(item.id) === Number(serverId));
    if (!server) return;

    const cpuPercent = Number.isFinite(server.cpu) ? server.cpu : null;
    const memPercent = Number.isFinite(server.mem) ? server.mem : null;
    const cpuWidth = Number.isFinite(cpuPercent) ? Math.round(cpuPercent) : 0;
    const memWidth = Number.isFinite(memPercent) ? Math.round(memPercent) : 0;

    const cpuFill = card.querySelector('[data-role="cpu-fill"]');
    const cpuValue = card.querySelector('[data-role="cpu-value"]');
    const memFill = card.querySelector('[data-role="mem-fill"]');
    const memValue = card.querySelector('[data-role="mem-value"]');

    if (cpuFill) cpuFill.style.width = `${cpuWidth}%`;
    if (cpuValue) cpuValue.textContent = formatPercent(cpuPercent);
    if (memFill) memFill.style.width = `${memWidth}%`;
    if (memValue) memValue.textContent = formatPercent(memPercent);

    updateServerNetworkBadgeInPlace(serverId);
}

async function refreshServerDynamicMetricsOnce() {
    if (state.currentView !== 'servers') return;
    const ok = await safeLoadServers({ silent: true });
    if (!ok || state.currentView !== 'servers') return;
    state.servers.forEach((server) => updateServerDynamicMetricsInPlace(server.id));
    await pingOfflineServers({ renderAfterEach: false });
}

function stopServerDynamicRefreshLoop() {
    if (state.serverDynamicTimerId) {
        window.clearInterval(state.serverDynamicTimerId);
        state.serverDynamicTimerId = null;
    }
}

function startServerDynamicRefreshLoop() {
    stopServerDynamicRefreshLoop();
    if (state.currentView !== 'servers') return;
    // [2026-04-24 11:41:37] 每 60 秒仅刷新动态字段，不触发整卡片重绘
    state.serverDynamicTimerId = window.setInterval(() => {
        refreshServerDynamicMetricsOnce();
    }, OFFLINE_PING_INTERVAL_MS);
}

function renderHomeView() {
    const pendingCount = Number(state.overview.pending_tasks || 0) + Number(state.overview.running_tasks || 0);
    const onlineCpuValues = state.servers.filter((item) => item.status === 'online' && Number.isFinite(item.cpu)).map((item) => item.cpu);
    const avgCpu = onlineCpuValues.length ? (onlineCpuValues.reduce((sum, value) => sum + value, 0) / onlineCpuValues.length).toFixed(1) : '0.0';
    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="summary-grid">
            <div class="summary-card"><i class="fas fa-server fa-2x"></i><h3>${state.servers.length}</h3><p>\u7269\u7406\u670d\u52a1\u5668</p><small>\u5728\u7ebf ${state.overview.online_servers || 0}</small></div>
            <div class="summary-card"><i class="fab fa-docker fa-2x"></i><h3>${state.dockerRows.length}</h3><p>\u5bb9\u5668\u5b9e\u4f8b</p><small>\u5f53\u524d\u73af\u5883\u5df2\u540c\u6b65\u5bb9\u5668</small></div>
            <div class="summary-card"><i class="fas fa-layer-group fa-2x"></i><h3>${state.dockerImages.length}</h3><p>\u955c\u50cf\u6570\u91cf</p><small>\u5f53\u524d\u73af\u5883\u5df2\u540c\u6b65\u955c\u50cf</small></div>
            <div class="summary-card"><i class="fas fa-chart-line"></i><h3>${avgCpu}%</h3><p>\u5e73\u5747 CPU \u8d1f\u8f7d</p><small>\u5f85\u5904\u7406\u4efb\u52a1 ${pendingCount}</small></div>
        </div>
        <!-- [2026-04-24 10:45:36] 首页文案改为通用业务说明，避免暴露临时调试信息 -->
        <div class="panel"><i class="fas fa-comment-dots"></i> <strong>平台说明</strong><br/>本页面用于统一查看服务器状态、容器镜像与交付件信息，支持按当前访问地址自动匹配 API 连接。</div>
    `;
}


function renderServersView() {
    let html = `${showErrorBanner()}<div class="server-grid">`;
    if (!state.servers.length) html += '<div class="empty-state">\u5f53\u524d\u6682\u65e0\u53ef\u7528\u670d\u52a1\u5668\u3002</div>';
    state.servers.forEach((server) => {
        const cpuPercent = Number.isFinite(server.cpu) ? server.cpu : null;
        const memPercent = Number.isFinite(server.mem) ? server.mem : null;
        const cpuWidth = Number.isFinite(cpuPercent) ? Math.round(cpuPercent) : 0;
        const memWidth = Number.isFinite(memPercent) ? Math.round(memPercent) : 0;
        const memoryHint = Number.isFinite(server.memoryUsedBytes) && Number.isFinite(server.memoryTotalBytes) && server.memoryTotalBytes > 0
            ? `<div class="metric-subtext">${formatBytes(server.memoryUsedBytes)} / ${formatBytes(server.memoryTotalBytes)}</div>`
            : '';
        // [2026-04-24 11:12:56] 精简提示文案，避免服务器卡片信息噪音
        const offlineHint = '';
        const isSelected = Number(server.id) === Number(state.selectedServerId);
        const networkBadge = networkStatusBadgeHtml(server);
        const ownerUsers = parseOwnerUsers(server.ownerUser);
        // [2026-04-24 11:46:15] 服务器名与详情 IP 相同则隐藏重复 IP 行
        const nameText = String(server.name || '').trim();
        const ipText = String(server.ip || '').trim();
        const ipLine = (nameText && ipText && nameText === ipText) ? '' : `IP：${escapeHtml(server.ip)}<br>`;

        html += `
            <div class="server-card ${isSelected ? 'is-selected' : ''}" data-server-card-id="${server.id}">
                <div class="server-row">
                    <div class="server-info">
                        <div class="server-name">
                            <i class="fas fa-hdd"></i>
                            <span>${escapeHtml(server.name)}</span>
                        </div>
                        <div class="status-group">
                            <span data-role="network-badge">${networkBadge}</span>
                        </div>
                        <div class="server-ip">${ipLine}\u64cd\u4f5c\u7cfb\u7edf\uff1a${escapeHtml(server.osName)} \uff5c \u8fd0\u884c\u65f6\uff1a${escapeHtml(server.runtime)}<br>\u6700\u8fd1\u5fc3\u8df3\uff1a${formatDate(server.lastSeenAt)}</div>
                    </div>
                    <div class="resource-metrics">
                        <div class="metric">
                            <div class="metric-label">CPU \u5360\u7528</div>
                            <div class="progress-bar-bg"><div class="progress-fill" data-role="cpu-fill" style="width: ${cpuWidth}%"></div></div>
                            <div class="metric-value" data-role="cpu-value">${formatPercent(cpuPercent)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">\u5185\u5b58\u5360\u7528</div>
                            <div class="progress-bar-bg"><div class="progress-fill" data-role="mem-fill" style="width: ${memWidth}%"></div></div>
                            <div class="metric-value" data-role="mem-value">${formatPercent(memPercent)}</div>
                            ${memoryHint}
                            ${offlineHint}
                        </div>
                        <label class="metric owner-metric">
                            <span class="metric-label">使用人</span>
                            <div class="owner-tags">
                                ${ownerUsers.length
                                    ? ownerUsers.map((name) => `<button type="button" class="owner-tag owner-remove-btn" data-server-id="${server.id}" data-owner-name="${escapeHtml(name)}"><span>${escapeHtml(name)}</span><span class="owner-remove-x">×</span></button>`).join('')
                                    : '<span class="metric-subtext">-</span>'}
                            </div>
                            <div class="owner-input-row">
                                <input class="owner-input owner-add-input" data-server-id="${server.id}" value="" placeholder="添加使用人">
                                <button class="action-btn owner-add-btn" type="button" data-server-id="${server.id}">添加</button>
                            </div>
                        </label>
                    </div>
                </div>
            </div>
        `;
    });
    html += `<div style="margin-top:20px; text-align:center; color:#6c7b94;">\u5171\u8ba1 ${state.servers.length} \u53f0\u670d\u52a1\u5668 \uff5c \u5728\u7ebf ${state.overview.online_servers || 0}</div></div>`;
    dynamicPanel.innerHTML = html;

    // [2026-04-24 15:31:45] 恢复卡片本体点击选中，保留防误触保护
    dynamicPanel.querySelectorAll('[data-server-card-id]').forEach((card) => {
        card.addEventListener('click', async (event) => {
            if (event.target.closest('.owner-input') || event.target.closest('.owner-input-row') || event.target.closest('.owner-add-btn') || event.target.closest('.owner-remove-btn')) return;
            const selectedText = window.getSelection ? String(window.getSelection().toString() || '').trim() : '';
            if (selectedText) return;
            if (!chooseServer(card.dataset.serverCardId)) return;
            await safeLoadDockerResources({ silent: true });
            renderServersView();
        });
    });

    async function appendOwnerUser(serverId, rawValue, input) {
        const nextUser = String(rawValue || '').trim();
        if (!nextUser) return;
        const matched = state.servers.find((item) => String(item.id) === String(serverId));
        const currentUsers = parseOwnerUsers(matched?.ownerUser || '');
        currentUsers.push(nextUser);
        const merged = joinOwnerUsers(currentUsers);
        try {
            await saveOwnerUser(serverId, merged);
            if (matched) {
                matched.ownerUser = merged;
                matched.reportedUser = merged || '-';
            }
            if (input) input.value = '';
            renderServersView();
            showToast('使用人已添加', 'success');
        } catch (error) {
            showToast(`保存使用人失败：${error.message}`, 'error');
        }
    }

    dynamicPanel.querySelectorAll('.owner-add-btn').forEach((button) => {
        button.addEventListener('click', async () => {
            const serverId = button.dataset.serverId;
            const input = dynamicPanel.querySelector(`.owner-add-input[data-server-id="${serverId}"]`);
            await appendOwnerUser(serverId, input?.value, input);
        });
    });

    dynamicPanel.querySelectorAll('.owner-add-input').forEach((input) => {
        input.addEventListener('keydown', async (event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            const serverId = input.dataset.serverId;
            await appendOwnerUser(serverId, input.value, input);
        });
    });

    // [2026-04-24 14:19:44] 使用人支持确认后删除
    dynamicPanel.querySelectorAll('.owner-remove-btn').forEach((button) => {
        button.addEventListener('click', async () => {
            const serverId = button.dataset.serverId;
            const ownerName = String(button.dataset.ownerName || '').trim();
            if (!ownerName) return;
            const ok = window.confirm(`确认删除使用人：${ownerName} ?`);
            if (!ok) return;

            const matched = state.servers.find((item) => String(item.id) === String(serverId));
            if (!matched) return;
            const nextUsers = parseOwnerUsers(matched.ownerUser || '').filter((name) => name !== ownerName);
            const merged = joinOwnerUsers(nextUsers);
            try {
                await saveOwnerUser(serverId, merged);
                matched.ownerUser = merged;
                matched.reportedUser = merged || '-';
                renderServersView();
                showToast('使用人已删除', 'success');
            } catch (error) {
                showToast(`删除使用人失败：${error.message}`, 'error');
            }
        });
    });
}


function renderDockerView() {
    // [2026-04-24 14:31:21] 容器列表“使用人”列后置，靠近操作列
    const containerRows = state.dockerRows.map((item) => `
        <tr>
            <td>${escapeHtml(item.server)}</td><td><code>${escapeHtml(item.containerName)}</code></td><td><code>${escapeHtml(item.imageName)}</code></td><td><span class="tag">${escapeHtml(statusText(item.status))}</span></td><td>${escapeHtml(item.ports)}</td><td>${escapeHtml(item.runningFor)}</td>
            <td><button class="action-btn" data-action="start-container" data-server-id="${item.serverId}" data-name="${escapeHtml(item.containerName)}">\u542f\u52a8</button><button class="action-btn" data-action="stop-container" data-server-id="${item.serverId}" data-name="${escapeHtml(item.containerName)}">\u505c\u6b62</button></td><td>${ownerTagsReadonlyHtml(item.serverId)}</td>
        </tr>
    `).join('');
    const imageRows = state.dockerImages.map((image) => `
        <tr>
            <td>${escapeHtml(image.repository)}</td><td>${escapeHtml(image.tag)}</td><td><code>${escapeHtml(image.id)}</code></td><td>${escapeHtml(image.digest)}</td><td>${escapeHtml(image.createdAt)}</td><td>${escapeHtml(image.size)}</td>
            <td><button class="action-btn" data-action="export-image" data-reference="${escapeHtml(image.reference)}">\u5bfc\u51fa\u955c\u50cf</button></td>
        </tr>
    `).join('');

    const serverSelector = state.servers.length
        ? `<label class="field docker-server-field"><span>\u670d\u52a1\u5668\u9009\u62e9</span><select id="dockerServerSelect">${dockerServerOptionsHtml()}</select></label>`
        : '<div class="info-banner">\u5f53\u524d\u6ca1\u6709\u53ef\u9009\u670d\u52a1\u5668\u3002</div>';

    const containerError = sanitizeDockerErrorMessage(state.dockerErrors.containers);
    const imageError = sanitizeDockerErrorMessage(state.dockerErrors.images);

    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="panel" style="margin-bottom:16px;">
            <div class="panel-head" style="margin-bottom:16px;">
                <div>
                    <h2 style="font-size:1.1rem;">\u5bb9\u5668\u4e0e\u955c\u50cf\u7ba1\u7406</h2>
                    <p>\u8bf7\u4ece\u4e0b\u62c9\u6846\u9009\u62e9\u670d\u52a1\u5668\u3002\u5bf9\u4e8e Agent \u79bb\u7ebf\u7684\u670d\u52a1\u5668\uff0c\u9875\u9762\u53ea\u663e\u793a\u72b6\u6001\uff0c\u4e0d\u518d\u989d\u5916\u5f39\u51fa\u79bb\u7ebf\u63d0\u793a\u3002</p>
                </div>
                <div class="section-actions">
                    <button class="action-btn" id="refreshDockerBtn"><i class="fas fa-sync-alt"></i>\u5237\u65b0\u5bb9\u5668\u548c\u955c\u50cf</button>
                </div>
            </div>
            ${serverSelector}
        </div>
        <div class="panel-stack">
            <div class="panel docker-section"><div class="panel-head" style="margin-bottom:16px;"><div><h3>\u5bb9\u5668\u5217\u8868</h3><p class="subtle-text">\u5982\u679c\u5bb9\u5668\u4e3a\u7a7a\u4f46\u955c\u50cf\u6b63\u5e38\uff0c\u8bf4\u660e\u5f53\u524d\u4e3b\u673a\u6ca1\u6709\u5bb9\u5668\uff0c\u6216\u63a5\u53e3\u8fd4\u56de\u4e3a\u7a7a\u3002</p></div><div class="tag">${state.dockerRows.length} \u4e2a\u5bb9\u5668</div></div>${showInlineBanner(containerError)}<table class="data-table"><thead><tr><th>\u670d\u52a1\u5668\u8282\u70b9</th><th>\u5bb9\u5668\u540d\u79f0</th><th>\u955c\u50cf\u540d\u79f0</th><th>\u72b6\u6001</th><th>\u7aef\u53e3</th><th>\u8fd0\u884c\u65f6\u957f</th><th>\u64cd\u4f5c</th><th>\u4f7f\u7528\u4eba</th></tr></thead><tbody>${containerRows || '<tr><td colspan="8">\u6682\u65e0\u5bb9\u5668\u6570\u636e\u3002</td></tr>'}</tbody></table></div>
            <div class="panel docker-section"><div class="panel-head" style="margin-bottom:16px;"><div><h3>\u955c\u50cf\u5217\u8868</h3><p class="subtle-text">\u955c\u50cf\u6570\u636e\u6765\u81ea\u63a5\u53e3 /servers/{id}/images\u3002</p></div><div class="tag">${state.dockerImages.length} \u4e2a\u955c\u50cf</div></div>${showInlineBanner(imageError)}<table class="data-table"><thead><tr><th>\u4ed3\u5e93</th><th>\u6807\u7b7e</th><th>\u955c\u50cf ID</th><th>Digest</th><th>\u521b\u5efa\u65f6\u95f4</th><th>\u5927\u5c0f</th><th>\u64cd\u4f5c</th></tr></thead><tbody>${imageRows || '<tr><td colspan="7">\u6682\u65e0\u955c\u50cf\u6570\u636e\u3002</td></tr>'}</tbody></table></div>
        </div>
    `;

    document.getElementById('dockerServerSelect')?.addEventListener('change', async (event) => {
        if (!chooseServer(event.target.value)) return;
        await safeLoadDockerResources({ silent: true });
        renderDockerView();
    });
    document.getElementById('refreshDockerBtn')?.addEventListener('click', async () => { await safeLoadDockerResources(); renderDockerView(); });
    dynamicPanel.querySelectorAll('button[data-action="start-container"]').forEach((button) => {
        button.addEventListener('click', async () => {
            try {
                await request(`/servers/${button.dataset.serverId}/containers/${encodeURIComponent(button.dataset.name)}/start`, { method: 'POST' });
                await safeLoadDockerResources({ silent: true });
                renderDockerView();
            } catch (error) {
                showToast(`启动失败：${error.message}`, 'error');
            }
        });
    });
    dynamicPanel.querySelectorAll('button[data-action="stop-container"]').forEach((button) => {
        button.addEventListener('click', async () => {
            try {
                await request(`/servers/${button.dataset.serverId}/containers/${encodeURIComponent(button.dataset.name)}/stop`, { method: 'POST' });
                await safeLoadDockerResources({ silent: true });
                renderDockerView();
            } catch (error) {
                showToast(`停止失败：${error.message}`, 'error');
            }
        });
    });
    dynamicPanel.querySelectorAll('button[data-action="export-image"]').forEach((button) => {
        button.addEventListener('click', async () => {
            if (!state.selectedServerId) return showToast('请先选择当前环境。', 'error');
            try {
                const result = await request(`/servers/${state.selectedServerId}/images/export`, { method: 'POST', body: JSON.stringify({ image_ref: button.dataset.reference }) });
                await Promise.allSettled([safeLoadArtifacts({ silent: true }), safeLoadTasks({ silent: true }), safeLoadOverview({ silent: true })]);
                showToast(`导出任务已提交：${result?.message || button.dataset.reference}`, 'success');
            } catch (error) {
                showToast(`导出失败：${error.message}`, 'error');
            }
        });
    });
}

function artifactCardsHtml() {
    if (!state.artifacts.length) return '<div class="artifact-card">当前暂无交付件，请先上传。</div>';
    return state.artifacts.map((artifact) => {
        const actions = [`<a class="action-btn" href="${api(`/artifacts/${artifact.id}/download`)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-download"></i> \u4e0b\u8f7d</a>`];
        if (artifact.kind === 'docker-image') actions.push(`<button class="action-btn" data-action="import-image" data-id="${artifact.id}"><i class="fas fa-file-import"></i> \u5bfc\u5165\u955c\u50cf</button>`);
        if (artifact.kind === 'compose-bundle') actions.push(`<button class="action-btn" data-action="deploy-compose" data-id="${artifact.id}"><i class="fas fa-rocket"></i> \u6267\u884c\u7f16\u6392\u90e8\u7f72</button>`);
        return `<div class="artifact-card"><div style="font-weight:700; font-size:1rem;">${escapeHtml(artifact.file_name)}</div><div class="artifact-meta">\u7c7b\u578b\uff1a${escapeHtml(artifact.kind)}<br>\u5927\u5c0f\uff1a${formatBytes(artifact.size_bytes)}<br>\u4e0a\u4f20\u65f6\u95f4\uff1a${formatDate(artifact.created_at)}</div><div class="artifact-actions">${actions.join('')}</div></div>`;
    }).join('');
}

function renderArtifactsView() {
    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="panel" style="margin-bottom:16px;">
            <div class="panel-head"><div><h2>交付件管理</h2><p>上传镜像包、部署包，并直接导入或部署到当前环境。</p></div><div class="section-actions"><button class="action-btn" id="refreshArtifactsBtn"><i class="fas fa-sync-alt"></i> 刷新</button></div></div>
            <div class="form-grid">
                <form class="form-card" id="artifactUploadForm"><h3>上传交付件</h3><label class="field"><span>文件</span><input id="artifactFileInput" type="file" required></label><label class="field"><span>类型</span><select id="artifactKindSelect"><option value="docker-image">镜像包</option><option value="compose-bundle">编排部署包</option><option value="generic">通用交付件</option></select></label><button class="action-btn primary" type="submit"><i class="fas fa-upload"></i> 上传到交付件管理</button></form>
                <div class="form-card"><h3>编排部署参数</h3><label class="field"><span>项目名</span><input id="composeProjectInput" placeholder="demo-app"></label><label class="field"><span>编排文件</span><input id="composeFileInput" value="docker-compose.yml"></label><label class="field"><span>工作目录</span><input id="composeWorkdirInput" placeholder="deploy 或 packages/app"></label><div class="info-banner">当前环境：${escapeHtml(state.selectedServerName || '未选择')}。如需导入或部署，请先在服务器列表中选定环境。</div></div>
            </div>
        </div>
        <div class="artifact-grid" id="artifactGridWrap">${artifactCardsHtml()}</div>
    `;
    document.getElementById('refreshArtifactsBtn')?.addEventListener('click', async () => { await safeLoadArtifacts(); renderArtifactsView(); });
    document.getElementById('artifactUploadForm')?.addEventListener('submit', async (event) => {
        event.preventDefault();
        const file = document.getElementById('artifactFileInput')?.files?.[0];
        const kind = document.getElementById('artifactKindSelect')?.value || 'generic';
        if (!file) return showToast('请先选择文件', 'error');
        try {
            const resp = await fetch(api('/artifacts/upload'), { method: 'POST', headers: { 'Content-Type': file.type || 'application/octet-stream', 'X-Artifact-Name': encodeURIComponent(file.name), 'X-Artifact-Kind': encodeURIComponent(kind), 'X-Artifact-Source': encodeURIComponent('customer-portal') }, body: file });
            await parseResponse(resp);
            await Promise.allSettled([safeLoadArtifacts({ silent: true }), safeLoadOverview({ silent: true })]);
            renderArtifactsView();
        } catch (error) { showToast(`上传失败：${error.message}`, 'error'); }
    });
    dynamicPanel.querySelectorAll('button[data-action="import-image"]').forEach((button) => {
        button.addEventListener('click', async () => {
            if (!state.selectedServerId) return showToast('请先在服务器列表里选择当前环境', 'error');
            try {
                await request(`/servers/${state.selectedServerId}/images/import`, { method: 'POST', body: JSON.stringify({ artifact_id: Number(button.dataset.id) }) });
                await Promise.allSettled([safeLoadTasks({ silent: true }), safeLoadOverview({ silent: true }), safeLoadDockerResources({ silent: true })]);
                renderArtifactsView();
            } catch (error) {
                showToast(`导入失败：${error.message}`, 'error');
            }
        });
    });
    dynamicPanel.querySelectorAll('button[data-action="deploy-compose"]').forEach((button) => {
        button.addEventListener('click', async () => {
            if (!state.selectedServerId) return showToast('请先在服务器列表里选择当前环境', 'error');
            try {
                await request(`/servers/${state.selectedServerId}/deployments/compose`, {
                    method: 'POST',
                    body: JSON.stringify({
                        artifact_id: Number(button.dataset.id),
                        project_name: document.getElementById('composeProjectInput')?.value.trim() || null,
                        compose_file: document.getElementById('composeFileInput')?.value.trim() || 'docker-compose.yml',
                        workdir: document.getElementById('composeWorkdirInput')?.value.trim() || null,
                    }),
                });
                await Promise.allSettled([safeLoadTasks({ silent: true }), safeLoadOverview({ silent: true }), safeLoadDockerResources({ silent: true })]);
                renderArtifactsView();
            } catch (error) {
                showToast(`部署失败：${error.message}`, 'error');
            }
        });
    });
}

function renderLocalImagesView() {
    // [2026-04-24 14:38:39] 新增本地镜像库视图：聚焦 docker-image 类型交付件
    const dockerImageArtifacts = state.artifacts.filter((artifact) => artifact.kind === 'docker-image');
    const cards = dockerImageArtifacts.map((artifact) => `
        <div class="artifact-card">
            <div style="font-weight:700; font-size:1rem;">${escapeHtml(artifact.file_name)}</div>
            <div class="artifact-meta">大小：${formatBytes(artifact.size_bytes)}<br>上传时间：${formatDate(artifact.created_at)}</div>
            <div class="artifact-actions">
                <a class="action-btn" href="${api(`/artifacts/${artifact.id}/download`)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-download"></i> 下载</a>
                <button class="action-btn" data-action="local-import-image" data-id="${artifact.id}"><i class="fas fa-file-import"></i> 导入镜像</button>
            </div>
        </div>
    `).join('');

    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="panel" style="margin-bottom:16px;">
            <div class="panel-head">
                <div><h2>本地镜像库</h2><p>展示交付件中的镜像包，可直接下载或导入当前环境。</p></div>
                <div class="section-actions"><button class="action-btn" id="refreshLocalImagesBtn"><i class="fas fa-sync-alt"></i> 刷新</button></div>
            </div>
            <div class="info-banner">当前环境：${escapeHtml(state.selectedServerName || '未选择')}。导入前请确认已在服务器列表选定环境。</div>
        </div>
        <div class="artifact-grid">${cards || '<div class="artifact-card">当前暂无镜像包交付件。</div>'}</div>
    `;

    document.getElementById('refreshLocalImagesBtn')?.addEventListener('click', async () => {
        await safeLoadArtifacts();
        renderLocalImagesView();
    });

    dynamicPanel.querySelectorAll('button[data-action="local-import-image"]').forEach((button) => {
        button.addEventListener('click', async () => {
            if (!state.selectedServerId) return showToast('请先在服务器列表里选择当前环境', 'error');
            try {
                await request(`/servers/${state.selectedServerId}/images/import`, { method: 'POST', body: JSON.stringify({ artifact_id: Number(button.dataset.id) }) });
                await Promise.allSettled([safeLoadTasks({ silent: true }), safeLoadOverview({ silent: true }), safeLoadDockerResources({ silent: true })]);
                showToast('镜像导入任务已提交', 'success');
            } catch (error) {
                showToast(`导入失败：${error.message}`, 'error');
            }
        });
    });
}

async function copyTextToClipboard(text) {
    // [2026-06-16 07:07:34] HTTP 内网页面可能禁用 Clipboard API，增加 textarea 兜底复制
    const value = String(text || '').trim();
    if (!value) return false;
    if (navigator.clipboard?.writeText && window.isSecureContext) {
        try {
            await navigator.clipboard.writeText(value);
            return true;
        } catch {}
    }

    const textarea = document.createElement('textarea');
    textarea.value = value;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {
        return document.execCommand('copy');
    } catch {
        return false;
    } finally {
        textarea.remove();
    }
}

// [2026-06-16 07:20:19] 自动复制仍失败时给出可选中文本框，避免 HTTP 内网页面只能报错
function promptManualCopyText(text) {
    const value = String(text || '').trim();
    if (!value) return;
    window.prompt('浏览器限制自动复制，请手动复制地址：', value);
}

function renderLocalResourcesView() {
    // [2026-04-24 14:43:47] 新增本地资源导航：聚合常用内网平台入口
    // [2026-06-16 06:59:56] 按清单回归简洁文字+按钮布局，保留数据平台入口但不再渲染卡片内额外图标
    // [2026-06-16 07:20:19] 108 的 11221 当前拒绝连接，数据平台入口改到已探测可访问的 11201
    const resources = [
        {
            name: 'GIT 服务器',
            url: 'http://10.250.30.108:3000/',
            desc: '代码仓库、分支管理与协作评审入口',
        },
        {
            name: '数据平台',
            url: 'http://10.250.30.108:11201/',
            desc: '数据任务、报表与平台服务入口',
        },
    ];

    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="panel" style="margin-bottom:16px;">
            <div class="panel-head">
                <div><h2>本地资源导航</h2><p>统一管理常用内网平台入口，点击可在新窗口打开。</p></div>
            </div>
        </div>
        <div class="summary-grid">
            ${resources.map((item) => `
                <div class="summary-card resource-card">
                    <div class="resource-card-head"><h3>${escapeHtml(item.name)}</h3></div>
                    <small>${escapeHtml(item.desc)}</small>
                    <div class="section-actions" style="margin-top:12px;">
                        <a class="action-btn" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer"><i class="fas fa-external-link-alt"></i> 打开</a>
                        <button class="action-btn" data-action="copy-resource-url" data-url="${escapeHtml(item.url)}"><i class="fas fa-copy"></i> 复制地址</button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    dynamicPanel.querySelectorAll('button[data-action="copy-resource-url"]').forEach((button) => {
        button.addEventListener('click', async () => {
            const url = button.dataset.url || '';
            const copied = await copyTextToClipboard(url);
            if (copied) {
                showToast('地址已复制', 'success');
                return;
            }
            promptManualCopyText(url);
            showToast('浏览器限制自动复制，已打开手动复制框', 'info');
        });
    });
}

function addMessage(role, content) {
    state.chatMessages.push({ role, content });
    renderChatMessages();
}

function renderChatMessages() {
    const container = document.getElementById('chatMessagesContainer');
    if (!container) return;
    container.innerHTML = '';
    state.chatMessages.forEach((msg) => {
        const div = document.createElement('div');
        div.className = `message ${msg.role === 'user' ? 'user' : 'agent'}`;
        div.innerHTML = `<div class="avatar">${msg.role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>'}</div><div class="bubble">${escapeHtml(msg.content).replace(/\n/g, '<br>')}</div>`;
        container.appendChild(div);
    });
    if (state.isWaiting) {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message agent';
        typingDiv.innerHTML = '<div class="avatar"><i class="fas fa-robot"></i></div><div class="bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
        container.appendChild(typingDiv);
    }
    container.scrollTop = container.scrollHeight;
}

function simulateAgentResponse(userInput) {
    return new Promise((resolve) => {
        setTimeout(() => {
            const lower = userInput.toLowerCase();
            if (lower.includes('\u5728\u7ebf') && lower.includes('\u4e3b\u673a')) {
                const onlineServers = state.servers.filter((item) => item.status === 'online');
                resolve(`\u5f53\u524d\u5728\u7ebf\u4e3b\u673a\uff1a\n${onlineServers.length ? onlineServers.map((item) => `- ${item.name} (${item.ip})`).join('\n') : '\u6682\u65e0\u5728\u7ebf\u4e3b\u673a'}`);
                return;
            }
            if (lower.includes('\u955c\u50cf')) { resolve(`\u5f53\u524d\u955c\u50cf\u6570\u91cf\uff1a${state.dockerImages.length}\u3002`); return; }
            if (lower.includes('\u5f53\u524d\u73af\u5883')) { resolve(`\u5f53\u524d\u73af\u5883\uff1a${state.selectedServerName || '\u672a\u9009\u62e9'}\u3002`); return; }
            if (lower.includes('\u4efb\u52a1')) { const pending = Number(state.overview.pending_tasks || 0) + Number(state.overview.running_tasks || 0); resolve(`\u5f85\u5904\u7406\u4efb\u52a1 ${pending} \u4e2a\uff0c\u6210\u529f\u4efb\u52a1 ${state.overview.success_tasks || 0} \u4e2a\u3002`); return; }
            resolve('\u4f60\u53ef\u4ee5\u8fd9\u6837\u95ee\u6211\uff1a\n- \u67e5\u770b\u5728\u7ebf\u4e3b\u673a\n- \u67e5\u770b\u5f53\u524d\u73af\u5883\n- \u67e5\u770b\u955c\u50cf\u6570\u91cf\n- \u67e5\u770b\u4efb\u52a1\u6570\u91cf');
        }, 900);
    });
}

async function sendUserMessage() {
    const input = document.getElementById('chatInput');
    const text = input.value.trim();
    if (!text || state.isWaiting) return;
    input.value = '';
    addMessage('user', text);
    state.isWaiting = true;
    renderChatMessages();
    const reply = await simulateAgentResponse(text);
    state.isWaiting = false;
    addMessage('agent', reply);
}
function renderAgentView() {
    dynamicPanel.innerHTML = `
        ${showErrorBanner()}
        <div class="agent-chat-container">
            <div class="chat-messages" id="chatMessagesContainer"></div>
            <div class="chat-input-area">
                <input type="text" id="chatInput" placeholder="\u4f8b\u5982\uff1a\u67e5\u770b\u5728\u7ebf\u4e3b\u673a / \u67e5\u770b\u955c\u50cf\u6570\u91cf" autocomplete="off">
                <button id="sendChatBtn"><i class="fas fa-paper-plane"></i> \u53d1\u9001</button>
            </div>
        </div>
    `;
    if (state.chatMessages.length === 0) {
        state.chatMessages = [];
        addMessage('agent', '\u4f60\u597d\uff01\u6211\u662f\u667a\u80fd\u8fd0\u7ef4\u52a9\u624b\u3002\n\n\u4f60\u53ef\u4ee5\u8fd9\u6837\u95ee\u6211\uff1a\n- \u67e5\u770b\u5728\u7ebf\u4e3b\u673a\n- \u67e5\u770b\u5f53\u524d\u73af\u5883\n- \u67e5\u770b\u955c\u50cf\u6570\u91cf\n- \u67e5\u770b\u4efb\u52a1\u6570\u91cf');
    } else {
        renderChatMessages();
    }
    document.getElementById('sendChatBtn')?.addEventListener('click', sendUserMessage);
    document.getElementById('chatInput')?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') sendUserMessage();
    });
}

async function safeLoadOverview(options = {}) { const { silent = false } = options; try { await loadOverview(); if (!silent) state.lastError = ''; return true; } catch (error) { if (!silent) state.lastError = error.message; return false; } }
async function safeLoadServers(options = {}) { const { silent = false } = options; try { await loadServers(); if (!silent) state.lastError = ''; return true; } catch (error) { if (!silent) state.lastError = error.message; return false; } }
async function safeLoadArtifacts(options = {}) { const { silent = false } = options; try { await loadArtifacts(); if (!silent) state.lastError = ''; return true; } catch (error) { if (!silent) state.lastError = error.message; return false; } }
async function safeLoadTasks(options = {}) { const { silent = false } = options; try { await loadTasks(); if (!silent) state.lastError = ''; return true; } catch (error) { if (!silent) state.lastError = error.message; return false; } }
async function safeLoadDockerResources(options = {}) { const { silent = false } = options; try { await loadDockerResources(); if (!silent) state.lastError = ''; return true; } catch (error) { if (!silent) state.lastError = error.message; return false; } }

function switchView(view) {
    // [2026-04-24 10:45:14] 保留 agent 入口可见，点击时仅提示暂未开放
    if (view === 'agent' && !ENABLE_AGENT_VIEW) {
        // [2026-05-21 01:55:19] 禁用入口只提示，不切换页面，避免标题与 active 状态错乱
        showToast('智能助手入口暂未开放，当前阶段仅支持查看与运维基础能力。', 'info');
        return;
    }
    state.currentView = view;
    document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.getAttribute('data-view') === view));
    setHeader(view);
    if (view !== 'servers') {
        stopOfflinePingLoop();
        stopServerDynamicRefreshLoop();
    }
    if (view === 'servers') {
        renderServersView();
        startOfflinePingLoop();
        startServerDynamicRefreshLoop();
        return;
    }
    if (view === 'docker') {
        state.lastError = '';
        renderDockerView();
        safeLoadDockerResources({ silent: true }).then(() => renderDockerView());
        return;
    }
    if (view === 'local-images') return renderLocalImagesView();
    if (view === 'local-resources') return renderLocalResourcesView();
    if (view === 'artifacts') return renderArtifactsView();
    if (view === 'agent') return renderAgentView();
    return renderHomeView();
}

function bindStaticEvents() {
    // [2026-04-24 10:45:14] 保留 agent 入口并置灰展示，避免误以为入口缺失
    if (!ENABLE_AGENT_VIEW) {
        const agentNav = document.querySelector('.nav-item[data-view="agent"]');
        if (agentNav) {
            agentNav.classList.add('is-disabled');
            agentNav.title = '智能助手暂未开放';
            // [2026-04-24 10:47:17] 保持主标签文字对齐，仅增加右侧状态徽标
            if (!agentNav.querySelector('.nav-item-note')) {
                const note = document.createElement('span');
                note.className = 'nav-item-note';
                note.textContent = '未开放';
                agentNav.appendChild(note);
            }
        }
    }
    document.getElementById('toggleSidebarBtn')?.addEventListener('click', () => sidebar.classList.toggle('collapsed'));
    document.querySelectorAll('.nav-item').forEach((item) => item.addEventListener('click', () => switchView(item.getAttribute('data-view'))));
    // [2026-04-24 10:45:36] 增加 API 地址可视化与手动覆盖能力
    document.getElementById('apiBaseBtn')?.addEventListener('click', () => {
        const current = getApiBase();
        const next = window.prompt('请输入 API Base（例如 http://127.0.0.1:8000/api）', current);
        if (next === null) return;
        const normalized = normalizeApiBase(next);
        if (!normalized) {
            showToast('API 地址不能为空', 'error');
            return;
        }
        try {
            new URL(normalized);
            localStorage.setItem(API_KEY, normalized);
            refreshApiBaseLabel();
            showToast(`API 已更新：${normalized}`, 'success');
            refreshAllData();
        } catch {
            showToast('API 地址格式无效', 'error');
        }
    });
    document.getElementById('helpBtn')?.addEventListener('click', async () => {
        try {
            const health = await request('/health');
            showToast(`当前 API：${getApiBase()} | 服务状态：${health.message}`, 'success');
        } catch (error) {
            showToast(`当前 API：${getApiBase()} | 服务连接失败：${error.message}`, 'error');
        }
    });
    document.getElementById('userBtn')?.addEventListener('click', () => showToast(`当前角色：管理员 | ${BUILD_TAG}`, 'info'));
}

async function refreshAllData() {
    const results = await Promise.allSettled([loadOverview(), loadServers(), loadArtifacts(), loadTasks()]);
    const firstRejected = results.find((item) => item.status === 'rejected');
    state.lastError = firstRejected ? (firstRejected.reason?.message || '\u6570\u636e\u52a0\u8f7d\u5931\u8d25') : '';
    await safeLoadDockerResources({ silent: true });
    switchView(state.currentView);
}

async function bootstrap() {
    restoreSelectedServer();
    // [2026-05-21 01:55:19] getApiBase 自行初始化缺省值，避免启动时覆盖用户手动 API 配置
    getApiBase();
    bindStaticEvents();
    refreshApiBaseLabel();
    switchView('home');
    await refreshAllData();
}

bootstrap();
