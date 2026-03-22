// GLM 使用量监控 - 前端逻辑

let autoRefreshTimer = null;
let historyChart = null;

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadStatus();
    loadConfig();
    loadHistory();

    // 绑定事件
    document.getElementById('btnRefresh').addEventListener('click', refreshData);
    document.getElementById('btnSettings').addEventListener('click', () => openModal('settingsModal'));
    document.getElementById('btnLogs').addEventListener('click', () => {
        openModal('logsModal');
        loadLogs();
    });
    document.getElementById('autoRefresh').addEventListener('change', toggleAutoRefresh);
    document.getElementById('refreshInterval').addEventListener('change', updateAutoRefresh);
});

// API 请求封装
async function api(endpoint, options = {}) {
    const response = await fetch(endpoint, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: '请求失败' }));
        throw new Error(error.error || '请求失败');
    }
    return response.json();
}

// 加载状态
async function loadStatus() {
    try {
        const status = await api('/api/status');
        updateStatusUI(status);

        if (status.lastUpdate) {
            document.getElementById('lastUpdate').textContent = formatTime(status.lastUpdate);
        }
    } catch (e) {
        console.error('加载状态失败:', e);
    }
}

// 更新状态UI
function updateStatusUI(status) {
    const indicator = document.getElementById('statusIndicator');
    const text = document.getElementById('statusText');

    if (status.configured) {
        indicator.classList.add('connected');
        indicator.classList.remove('loading');
        text.textContent = status.github_configured ? '已配置 (含GitHub同步)' : '已配置';
    } else {
        indicator.classList.remove('connected');
        text.textContent = '未配置';
    }

    // 恢复自动刷新设置
    document.getElementById('autoRefresh').checked = status.auto_refresh;
    document.getElementById('refreshInterval').value = status.refresh_interval;

    if (status.auto_refresh) {
        startAutoRefresh(status.refresh_interval);
    }
}

// 加载配置
async function loadConfig() {
    try {
        const config = await api('/api/config');
        if (config.zhipu_cookie) {
            document.getElementById('zhipuCookie').placeholder = '***已设置***';
        }
        if (config.github_token) {
            document.getElementById('githubToken').placeholder = '***已设置***';
        }
        document.getElementById('githubRepo').value = config.github_repo || '';
    } catch (e) {
        console.error('加载配置失败:', e);
    }
}

// 保存设置
async function saveSettings() {
    const cookie = document.getElementById('zhipuCookie').value;
    const token = document.getElementById('githubToken').value;
    const repo = document.getElementById('githubRepo').value;
    const autoRefresh = document.getElementById('autoRefresh').checked;
    const interval = parseInt(document.getElementById('refreshInterval').value);

    const config = {
        auto_refresh: autoRefresh,
        refresh_interval: interval
    };

    if (cookie && !cookie.startsWith('***')) {
        config.zhipu_cookie = cookie;
    }
    if (token && !token.startsWith('***')) {
        config.github_token = token;
    }
    if (repo) {
        config.github_repo = repo;
    }

    try {
        await api('/api/config', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        showToast('设置已保存', 'success');
        closeModal('settingsModal');
        loadStatus();
    } catch (e) {
        showToast('保存失败: ' + e.message, 'error');
    }
}

// 刷新数据
async function refreshData() {
    const btn = document.getElementById('btnRefresh');
    const indicator = document.getElementById('statusIndicator');

    btn.disabled = true;
    btn.textContent = '⏳ 获取中...';
    indicator.classList.add('loading');

    showLoading(true);

    try {
        const data = await api('/api/usage');

        updateQuotaUI(data);
        document.getElementById('lastUpdate').textContent = formatTime(data.timestamp);

        showToast('数据已更新', 'success');
        loadHistory(); // 刷新图表
    } catch (e) {
        showToast('获取失败: ' + e.message, 'error');
        console.error(e);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 立即刷新';
        indicator.classList.remove('loading');
        showLoading(false);
    }
}

// 更新配额UI
function updateQuotaUI(data) {
    // 5小时额度
    const hourly = data.hourly_quota_percent;
    if (hourly !== null && hourly !== undefined) {
        const hourlyEl = document.getElementById('hourlyPercent');
        const hourlyBar = document.getElementById('hourlyBar');

        hourlyEl.textContent = hourly.toFixed(1) + '%';
        hourlyBar.style.width = hourly + '%';

        // 颜色
        const level = hourly > 80 ? 'high' : hourly > 50 ? 'medium' : 'low';
        hourlyEl.className = 'quota-value ' + level;
        hourlyBar.className = 'quota-fill ' + level;
    }

    // 每周额度
    const weekly = data.weekly_quota_percent;
    if (weekly !== null && weekly !== undefined) {
        const weeklyEl = document.getElementById('weeklyPercent');
        const weeklyBar = document.getElementById('weeklyBar');

        weeklyEl.textContent = weekly.toFixed(1) + '%';
        weeklyBar.style.width = weekly + '%';

        const level = weekly > 80 ? 'high' : weekly > 50 ? 'medium' : 'low';
        weeklyEl.className = 'quota-value ' + level;
        weeklyBar.className = 'quota-fill ' + level;
    }

    // 详细数据（如果有的话）
    if (data.hourly_used) {
        document.getElementById('hourlyUsed').textContent = formatNumber(data.hourly_used);
    }
    if (data.hourly_total) {
        document.getElementById('hourlyTotal').textContent = formatNumber(data.hourly_total);
    }
    if (data.weekly_used) {
        document.getElementById('weeklyUsed').textContent = formatNumber(data.weekly_used);
    }
    if (data.weekly_total) {
        document.getElementById('weeklyTotal').textContent = formatNumber(data.weekly_total);
    }
}

// 加载历史数据
async function loadHistory() {
    try {
        const history = await api('/api/usage/history');
        if (history.length > 0) {
            // 更新最新数据
            updateQuotaUI(history[history.length - 1]);
            // 绘制图表
            drawChart(history);
        }
    } catch (e) {
        console.error('加载历史失败:', e);
    }
}

// 绘制图表
function drawChart(data) {
    const ctx = document.getElementById('historyChart').getContext('2d');

    if (historyChart) {
        historyChart.destroy();
    }

    const labels = data.map(d => new Date(d.timestamp));
    const hourlyData = data.map(d => d.hourly_quota_percent);
    const weeklyData = data.map(d => d.weekly_quota_percent);

    historyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '5小时额度 %',
                    data: hourlyData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2
                },
                {
                    label: '每周额度 %',
                    data: weeklyData,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8' }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            hour: 'MM-dd HH:mm'
                        }
                    },
                    ticks: { color: '#64748b', maxTicksLimit: 10 },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                },
                y: {
                    min: 0,
                    max: 100,
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(255,255,255,0.1)' }
                }
            }
        }
    });
}

// 加载日志
async function loadLogs() {
    const lines = document.getElementById('logLines').value;
    try {
        const result = await api(`/api/logs?lines=${lines}`);
        document.getElementById('logsContent').textContent = result.logs || '暂无日志';
    } catch (e) {
        document.getElementById('logsContent').textContent = '加载日志失败: ' + e.message;
    }
}

// 自动刷新
function toggleAutoRefresh() {
    const enabled = document.getElementById('autoRefresh').checked;
    if (enabled) {
        const interval = parseInt(document.getElementById('refreshInterval').value);
        startAutoRefresh(interval);
        saveAutoRefreshSetting(true, interval);
    } else {
        stopAutoRefresh();
        saveAutoRefreshSetting(false, 30);
    }
}

function updateAutoRefresh() {
    if (document.getElementById('autoRefresh').checked) {
        const interval = parseInt(document.getElementById('refreshInterval').value);
        stopAutoRefresh();
        startAutoRefresh(interval);
        saveAutoRefreshSetting(true, interval);
    }
}

function startAutoRefresh(minutes) {
    stopAutoRefresh();
    autoRefreshTimer = setInterval(refreshData, minutes * 60 * 1000);
    console.log(`自动刷新已启动: 每${minutes}分钟`);
}

function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
}

async function saveAutoRefreshSetting(enabled, interval) {
    await api('/api/config', {
        method: 'POST',
        body: JSON.stringify({
            auto_refresh: enabled,
            refresh_interval: interval
        })
    });
}

// 弹窗控制
function openModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

// 点击弹窗外部关闭
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('show');
        }
    });
});

// 加载提示
function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'flex' : 'none';
}

// Toast 消息
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = 'toast show ' + type;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// 格式化时间
function formatTime(isoString) {
    return new Date(isoString).toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 格式化数字
function formatNumber(num) {
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toLocaleString();
}
