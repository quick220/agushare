/* ─── A股大屏 前端主逻辑 ─────────────────────────── */

const API_BASE = window.location.origin + '/api';
const REFRESH_INTERVAL = 5000; // 5秒刷新

// ─── 颜色辅助 ────────────────────────────────────
function getColor(pct) {
    if (pct > 0) return '#e74c3c';
    if (pct < 0) return '#2ecc71';
    return '#8892b0';
}

function getBgClass(pct) {
    if (pct > 0) return 'bg-up';
    if (pct < 0) return 'bg-down';
    return '';
}

function formatPct(pct) {
    const s = pct > 0 ? '+' : '';
    return s + pct.toFixed(2) + '%';
}

function formatAmount(val) {
    if (val >= 10000) return (val / 10000).toFixed(2) + '万亿';
    if (val >= 1) return val.toFixed(2) + '亿';
    return (val * 10000).toFixed(0) + '万';
}

// ─── 更新三大指数 ────────────────────────────────
function updateIndices(data) {
    const indices = [
        { code: 'sh000001', name: '上证指数' },
        { code: 'sz399001', name: '深证成指' },
        { code: 'sz399006', name: '创业板指' },
    ];

    indices.forEach((item, idx) => {
        const card = document.getElementById(`index-${idx + 1}`);
        if (!card) return;

        const d = data[item.code];
        if (!d) return;

        const pct = d.change_pct || 0;
        const direction = pct > 0 ? 'up' : (pct < 0 ? 'down' : 'even');
        const colorClass = pct > 0 ? 'up-text' : (pct < 0 ? 'down-text' : 'even-text');

        card.className = `index-card ${direction}`;
        card.innerHTML = `
            <div class="index-info">
                <div class="index-name">${item.name}</div>
                <div class="index-price ${colorClass}">${d.price.toFixed(2)}</div>
            </div>
            <div class="index-change">
                <div class="index-pct ${colorClass}">${formatPct(pct)}</div>
                <div class="index-amount">成交 ${d.amount ? d.amount.toFixed(1) + '亿' : '--'}</div>
            </div>
        `;
    });

    // 市场状态
    const status = data['_market_status'];
    const statusDot = document.getElementById('market-status-dot');
    const statusText = document.getElementById('market-status-text');
    if (statusDot && statusText) {
        if (status === 'open') {
            statusDot.className = 'status-dot open';
            statusText.textContent = '交易中';
            statusText.style.color = '#2ecc71';
        } else {
            statusDot.className = 'status-dot closed';
            statusText.textContent = '已收盘';
            statusText.style.color = '#e74c3c';
        }
    }
}

// ─── 更新自选股列表 ──────────────────────────────
function updateStocks(data) {
    const tbody = document.getElementById('stock-list');
    if (!tbody) return;

    let html = '';
    let count = 0;

    for (const [code, d] of Object.entries(data)) {
        const pct = d.change_pct || 0;
        const price = d.price || 0;
        html += `
            <div class="stock-row">
                <div class="stock-name">${d.name || code}</div>
                <div class="stock-price" style="color:${getColor(pct)}">${price.toFixed(2)}</div>
                <div class="stock-pct ${getBgClass(pct)}">${formatPct(pct)}</div>
                <div class="stock-turnover">${d.turnover || '--'}</div>
            </div>
        `;
        count++;
    }

    tbody.innerHTML = html;

    // 更新股票数量
    const countEl = document.getElementById('stock-count');
    if (countEl) countEl.textContent = `${count} 只`;
}

// ─── 更新涨跌家数饼图 ────────────────────────────
let pieChart = null;

function initPieChart() {
    const dom = document.getElementById('pie-chart');
    if (!dom) return;
    pieChart = echarts.init(dom, 'dark');
}

function updatePieChart(data) {
    if (!pieChart) initPieChart();
    if (!pieChart) return;

    const option = {
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} ({d}%)',
            backgroundColor: 'rgba(10, 14, 26, 0.9)',
            borderColor: '#2a3050',
            textStyle: { color: '#e0e6ff', fontSize: 14 },
        },
        legend: {
            orient: 'vertical',
            right: '5%',
            top: 'center',
            textStyle: { color: '#8892b0', fontSize: 13 },
            itemWidth: 14,
            itemHeight: 14,
        },
        series: [{
            type: 'pie',
            radius: ['45%', '70%'],
            center: ['40%', '55%'],
            avoidLabelOverlap: false,
            label: {
                show: true,
                formatter: '{c}',
                color: '#e0e6ff',
                fontSize: 16,
                fontWeight: 'bold',
            },
            emphasis: {
                label: { show: true, fontSize: 20, fontWeight: 'bold' },
                itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' },
            },
            labelLine: { show: false },
            data: [
                {
                    value: data.advance || 0,
                    name: '上涨',
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#e74c3c' },
                            { offset: 1, color: '#c0392b' },
                        ]),
                        shadowBlur: 8,
                        shadowColor: 'rgba(231, 76, 60, 0.4)',
                    },
                },
                {
                    value: data.decline || 0,
                    name: '下跌',
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#2ecc71' },
                            { offset: 1, color: '#27ae60' },
                        ]),
                        shadowBlur: 8,
                        shadowColor: 'rgba(46, 204, 113, 0.4)',
                    },
                },
                {
                    value: data.even || 0,
                    name: '平盘',
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: '#8892b0' },
                            { offset: 1, color: '#5a6480' },
                        ]),
                        shadowBlur: 8,
                        shadowColor: 'rgba(136, 146, 176, 0.4)',
                    },
                },
            ],
        }],
        backgroundColor: 'transparent',
    };

    pieChart.setOption(option, true);
}

// ─── 更新分时走势图 ──────────────────────────────
let timelineChart = null;
let timelineData = [];

function initTimelineChart() {
    const dom = document.getElementById('timeline-chart');
    if (!dom) return;
    timelineChart = echarts.init(dom, 'dark');
}

function updateTimelineChart(indices) {
    if (!timelineChart) initTimelineChart();
    if (!timelineChart) return;

    const sh = indices['sh000001'];
    if (!sh || !sh.price) return;

    const now = new Date();
    const h = now.getHours();
    const m = now.getMinutes();

    // 模拟过去的分时数据点（实际部署时可改为真实分时API）
    timelineData.push({
        time: `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`,
        value: sh.price,
    });

    // 保留最近 240 个点（约等于全天4小时每分钟一个点）
    if (timelineData.length > 240) {
        timelineData = timelineData.slice(-240);
    }

    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(10, 14, 26, 0.9)',
            borderColor: '#2a3050',
            textStyle: { color: '#e0e6ff', fontSize: 12 },
            formatter: function (params) {
                const p = params[0];
                if (!p) return '';
                const prevClose = sh.prev_close || sh.price;
                const pct = ((p.value - prevClose) / prevClose * 100).toFixed(2);
                const color = pct > 0 ? '#e74c3c' : (pct < 0 ? '#2ecc71' : '#8892b0');
                return `<div style="font-size:12px">${p.axisValue}</div>
                        <div style="font-size:14px;font-weight:bold">${p.value.toFixed(2)}</div>
                        <div style="color:${color};font-size:12px">${pct > 0 ? '+' : ''}${pct}%</div>`;
            },
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            top: '5%',
            containLabel: true,
        },
        xAxis: {
            type: 'category',
            data: timelineData.map(d => d.time),
            axisLine: { lineStyle: { color: '#2a3050' } },
            axisLabel: { color: '#4a5580', fontSize: 10, interval: 30 },
            splitLine: { show: false },
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: 'rgba(42, 48, 80, 0.5)', type: 'dashed' } },
            axisLabel: { color: '#4a5580', fontSize: 10 },
            axisLine: { show: false },
        },
        series: [{
            type: 'line',
            data: timelineData.map(d => d.value),
            smooth: true,
            showSymbol: false,
            lineStyle: {
                width: 2,
                color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                    { offset: 0, color: '#7c4dff' },
                    { offset: 0.5, color: '#00d4ff' },
                    { offset: 1, color: '#7c4dff' },
                ]),
            },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: 'rgba(0, 212, 255, 0.15)' },
                    { offset: 1, color: 'rgba(0, 212, 255, 0.02)' },
                ]),
            },
        }],
        backgroundColor: 'transparent',
    };

    timelineChart.setOption(option, true);
}

// ─── 自适应 ──────────────────────────────────────
function handleResize() {
    if (pieChart) pieChart.resize();
    if (timelineChart) timelineChart.resize();
}

window.addEventListener('resize', handleResize);

// ─── 主数据请求 ──────────────────────────────────
async function fetchAll() {
    try {
        const resp = await fetch(`${API_BASE}/all`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();

        updateIndices(data.indices || {});
        updateStocks(data.stocks || {});
        updatePieChart(data.market_overview || { advance: 0, decline: 0, even: 0 });

        if (data.indices && data.indices['sh000001'] && data.indices['sh000001'].price > 0) {
            updateTimelineChart(data.indices);
        }

        // 更新时间
        const timeEl = document.getElementById('update-time');
        if (timeEl) timeEl.textContent = data.update_time || '--:--:--';

    } catch (err) {
        console.error('数据获取失败:', err);
    }
}

// ─── 启动 ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initPieChart();
    initTimelineChart();
    fetchAll();
    setInterval(fetchAll, REFRESH_INTERVAL);
});

// ═══════════════════════════════════════════════════════
// 自选股管理
// ═══════════════════════════════════════════════════════

function openManageModal() {
    document.getElementById('manage-modal').classList.add('active');
    document.getElementById('add-result').textContent = '';
    document.getElementById('add-result').className = 'add-result';
    document.getElementById('add-code').value = '';
    document.getElementById('add-name').value = '';
    loadManageList();
}

function closeManageModal(e) {
    if (e && e.target !== e.currentTarget) return;
    document.getElementById('manage-modal').classList.remove('active');
}

async function loadManageList() {
    try {
        const resp = await fetch(`${API_BASE}/watchlist`);
        const data = await resp.json();
        const list = data.stocks || [];

        document.getElementById('manage-count').textContent = list.length;

        const container = document.getElementById('manage-list');
        container.innerHTML = list.map(s => `
            <div class="manage-item">
                <div>
                    <span class="mi-name">${s.name}</span>
                    <span class="mi-code">${s.code}</span>
                </div>
                <button class="btn-remove" onclick="removeStock('${s.code}')">删除</button>
            </div>
        `).join('');
    } catch (err) {
        console.error('加载自选股列表失败:', err);
    }
}

async function addStock() {
    const exchange = document.getElementById('add-exchange').value;
    const codeRaw = document.getElementById('add-code').value.trim();
    const name = document.getElementById('add-name').value.trim();
    const resultEl = document.getElementById('add-result');

    if (!codeRaw || codeRaw.length !== 6 || !/^\d{6}$/.test(codeRaw)) {
        resultEl.textContent = '❌ 请输入6位数字股票代码';
        resultEl.className = 'add-result error';
        return;
    }
    if (!name) {
        resultEl.textContent = '❌ 请输入股票名称';
        resultEl.className = 'add-result error';
        return;
    }

    const code = exchange + codeRaw;

    try {
        const resp = await fetch(`${API_BASE}/watchlist/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, name }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        const result = await resp.json();
        resultEl.textContent = `✅ 已添加 ${name} (${result.count}只)`;
        resultEl.className = 'add-result success';

        document.getElementById('add-code').value = '';
        document.getElementById('add-name').value = '';
        loadManageList();
    } catch (err) {
        resultEl.textContent = `❌ ${err.message}`;
        resultEl.className = 'add-result error';
    }
}

async function removeStock(code) {
    try {
        const resp = await fetch(`${API_BASE}/watchlist/${code}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error('删除失败');
        loadManageList();
    } catch (err) {
        console.error('删除失败:', err);
    }
}
