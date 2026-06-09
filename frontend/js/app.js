/* ─── A股大屏 前端主逻辑 ─────────────────────────── */

const API_BASE = window.location.origin + '/api';
const REFRESH_MAIN = 5000;
const REFRESH_INTRADAY = 30000;
const REFRESH_KLINE = 300000; // 5 min

// ─── 颜色辅助 ────────────────────────────────────
function getColor(pct) {
    if (pct > 0) return '#e74c3c';
    if (pct < 0) return '#2ecc71';
    return '#8892b0';
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

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ─── 更新三大指数 ────────────────────────────────
function updateIndices(data) {
    const indices = [
        { code: 'sh000001', name: '上证指数' },
        { code: 'sz399001', name: '深证成指' },
        { code: 'sz399006', name: '创业板指' },
        { code: 'sh000688', name: '科创50' },
        { code: 'bj899050', name: '北证50' },
        { code: 'sh518880', name: '黄金ETF' },
    ];

    indices.forEach((item, idx) => {
        const card = document.getElementById('index-' + (idx + 1));
        if (!card) return;
        const d = data[item.code];
        if (!d) return;

        const pct = d.change_pct || 0;
        const direction = pct > 0 ? 'up' : (pct < 0 ? 'down' : 'even');
        const colorClass = pct > 0 ? 'up-text' : (pct < 0 ? 'down-text' : 'even-text');

        card.className = 'index-card ' + direction;
        card.innerHTML = '<div class="index-info">'
            + '<div class="index-name">' + item.name + '</div>'
            + '<div class="index-price ' + colorClass + '">' + (d.price || 0).toFixed(2) + '</div>'
            + '</div>'
            + '<div class="index-change">'
            + '<div class="index-pct ' + colorClass + '">' + formatPct(pct) + '</div>'
            + '<div class="index-amount">成交 ' + (d.amount ? d.amount.toFixed(1) + '亿' : '--') + '</div>'
            + '</div>';
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

    for (const code in data) {
        const d = data[code];
        const pct = d.change_pct || 0;
        const price = d.price || 0;
        html += '<div class="stock-row">'
            + '<div class="stock-name">' + (d.name || code) + '</div>'
            + '<div class="stock-price" style="color:' + getColor(pct) + '">' + price.toFixed(2) + '</div>'
            + '<div class="stock-pct ' + (pct > 0 ? 'bg-up' : (pct < 0 ? 'bg-down' : '')) + '">' + formatPct(pct) + '</div>'
            + '<div class="stock-turnover">' + (d.turnover || '--') + '</div>'
            + '</div>';
        count++;
    }

    tbody.innerHTML = html;

    const countEl = document.getElementById('stock-count');
    if (countEl) countEl.textContent = count + ' 只';
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
            textStyle: { color: '#e0e6ff', fontSize: 11 },
        },
        legend: {
            orient: 'horizontal',
            bottom: 0,
            textStyle: { color: '#8892b0', fontSize: 10 },
            itemWidth: 10,
            itemHeight: 10,
        },
        series: [{
            type: 'pie',
            radius: ['40%', '65%'],
            center: ['50%', '45%'],
            avoidLabelOverlap: false,
            label: {
                show: true,
                formatter: '{c}',
                color: '#e0e6ff',
                fontSize: 13,
                fontWeight: 'bold',
            },
            emphasis: {
                label: { show: true, fontSize: 16, fontWeight: 'bold' },
                itemStyle: { shadowBlur: 8, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' },
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
                        shadowBlur: 6,
                        shadowColor: 'rgba(231, 76, 60, 0.3)',
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
                        shadowBlur: 6,
                        shadowColor: 'rgba(46, 204, 113, 0.3)',
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
                        shadowBlur: 6,
                        shadowColor: 'rgba(136, 146, 176, 0.3)',
                    },
                },
            ],
        }],
        backgroundColor: 'transparent',
    };

    pieChart.setOption(option, true);
}

// ─── 更新分时走势图（真实数据）────────────────────
let timelineChart = null;

function initTimelineChart() {
    const dom = document.getElementById('timeline-chart');
    if (!dom) return;
    timelineChart = echarts.init(dom, 'dark');
}

function updateTimelineChart(intradayData) {
    if (!timelineChart) initTimelineChart();
    if (!timelineChart) return;

    const trends = intradayData.trends || [];
    if (trends.length === 0) return;

    const times = trends.map(t => {
        const parts = (t.time || '').split(' ');
        return parts[parts.length - 1].substring(0, 5);
    });
    const prices = trends.map(t => t.price);

    // 计算基准价和涨跌幅颜色
    const prePrice = intradayData.prePrice || prices[0];
    const lastPrice = prices[prices.length - 1];
    const isUp = lastPrice >= prePrice;

    const lineColor = isUp ? '#e74c3c' : '#2ecc71';
    const areaColor = isUp
        ? ['rgba(231, 76, 60, 0.15)', 'rgba(231, 76, 60, 0.02)']
        : ['rgba(46, 204, 113, 0.15)', 'rgba(46, 204, 113, 0.02)'];

    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const pad = (maxP - minP) * 0.08 || prePrice * 0.005;

    const option = {
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(10, 14, 26, 0.9)',
            borderColor: '#2a3050',
            textStyle: { color: '#e0e6ff', fontSize: 11 },
            formatter: function (params) {
                const p = params[0];
                if (!p) return '';
                const pct = ((p.value - prePrice) / prePrice * 100).toFixed(2);
                const color = pct > 0 ? '#e74c3c' : (pct < 0 ? '#2ecc71' : '#8892b0');
                return '<div style="font-size:11px">' + p.axisValue + '</div>'
                    + '<div style="font-size:13px;font-weight:bold">' + p.value.toFixed(2) + '</div>'
                    + '<div style="color:' + color + ';font-size:11px">' + (pct > 0 ? '+' : '') + pct + '%</div>';
            },
        },
        grid: { left: '8%', right: '4%', bottom: '8%', top: '6%' },
        xAxis: {
            type: 'category',
            data: times,
            axisLine: { lineStyle: { color: '#2a3050' } },
            axisLabel: {
                color: '#4a5580',
                fontSize: 9,
                interval: function (idx, count) {
                    if (count <= 20) return true;
                    const step = Math.ceil(count / 8);
                    return idx % step === 0;
                },
            },
            splitLine: { show: false },
        },
        yAxis: {
            type: 'value',
            min: minP - pad,
            max: maxP + pad,
            splitLine: { lineStyle: { color: 'rgba(42, 48, 80, 0.4)', type: 'dashed' } },
            axisLabel: { color: '#4a5580', fontSize: 9 },
            axisLine: { show: false },
        },
        series: [{
            type: 'line',
            data: prices,
            smooth: true,
            showSymbol: false,
            lineStyle: { width: 2, color: lineColor },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: areaColor[0] },
                    { offset: 1, color: areaColor[1] },
                ]),
            },
            markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: { color: '#4a5580', type: 'dashed', width: 1 },
                label: { show: true, color: '#4a5580', fontSize: 9, formatter: '昨收 ' + prePrice.toFixed(2) },
                data: [{ yAxis: prePrice }],
            },
        }],
        backgroundColor: 'transparent',
    };

    timelineChart.setOption(option, true);
}

// ─── 更新K线图 ──────────────────────────────────
let klineChart = null;

function initKlineChart() {
    const dom = document.getElementById('kline-chart');
    if (!dom) return;
    klineChart = echarts.init(dom, 'dark');
}

function renderKlineChart(data) {
    if (!klineChart) initKlineChart();
    if (!klineChart) return;

    const klines = data.klines || [];
    if (klines.length === 0) return;

    const dates = klines.map(k => k.date.substring(5));
    const ohlc = klines.map(k => [k.open, k.close, k.low, k.high]);
    const volumes = klines.map(k => k.volume);
    const pcts = klines.map(k => k.pct);

    // 成交量颜色：涨红色跌绿色
    const volColors = klines.map(k => k.close >= k.open ? '#e74c3c' : '#2ecc71');

    // 计算MA
    function calcMA(data, days) {
        const result = [];
        for (let i = 0; i < data.length; i++) {
            if (i < days - 1) {
                result.push('-');
            } else {
                let sum = 0;
                for (let j = i - days + 1; j <= i; j++) {
                    sum += data[j];
                }
                result.push((sum / days).toFixed(2));
            }
        }
        return result;
    }

    const closePrices = klines.map(k => k.close);
    const ma5 = calcMA(closePrices, 5);
    const ma10 = calcMA(closePrices, 10);
    const ma20 = calcMA(closePrices, 20);

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(10, 14, 26, 0.95)',
            borderColor: '#2a3050',
            textStyle: { color: '#e0e6ff', fontSize: 11 },
        },
        grid: [
            { left: '6%', right: '4%', top: '8%', height: '62%' },
            { left: '6%', right: '4%', top: '78%', height: '18%' },
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: '#2a3050' } },
                axisLabel: {
                    color: '#4a5580',
                    fontSize: 9,
                    interval: function (idx, count) {
                        const step = Math.max(1, Math.ceil(count / 10));
                        return idx % step === 0;
                    },
                },
                splitLine: { show: false },
                gridIndex: 0,
            },
            {
                type: 'category',
                data: dates,
                axisLine: { lineStyle: { color: '#2a3050' } },
                axisLabel: { show: false },
                gridIndex: 1,
                splitLine: { show: false },
            },
        ],
        yAxis: [
            {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: 'rgba(42, 48, 80, 0.4)', type: 'dashed' } },
                axisLabel: { color: '#4a5580', fontSize: 9 },
                axisLine: { show: false },
                gridIndex: 0,
            },
            {
                type: 'value',
                scale: true,
                splitLine: { show: false },
                axisLabel: { show: false },
                axisLine: { show: false },
                gridIndex: 1,
            },
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: ohlc,
                xAxisIndex: 0,
                yAxisIndex: 0,
                itemStyle: {
                    color: '#e74c3c',
                    color0: '#2ecc71',
                    borderColor: '#e74c3c',
                    borderColor0: '#2ecc71',
                },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    lineStyle: { color: '#4a5580', type: 'dashed', width: 1 },
                    label: { show: true, color: '#4a5580', fontSize: 9, formatter: function(p) { return p.value.toFixed(0); } },
                    data: [
                        { type: 'average', name: '均线' },
                    ],
                },
            },
            {
                name: 'MA5',
                type: 'line',
                data: ma5,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#f0d060' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            {
                name: 'MA10',
                type: 'line',
                data: ma10,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#60b0f0' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            {
                name: 'MA20',
                type: 'line',
                data: ma20,
                smooth: true,
                showSymbol: false,
                lineStyle: { width: 1, color: '#f060b0' },
                xAxisIndex: 0,
                yAxisIndex: 0,
            },
            {
                name: '成交量',
                type: 'bar',
                data: volumes.map((v, i) => ({
                    value: v,
                    itemStyle: { color: volColors[i] },
                })),
                xAxisIndex: 1,
                yAxisIndex: 1,
            },
        ],
        backgroundColor: 'transparent',
    };

    klineChart.setOption(option, true);
}

// ─── 更新纵列快讯 ────────────────────────────────
function updateNews(data) {
    const container = document.getElementById('news-list');
    if (!container) return;

    const items = (data && data.items) || [];
    const countEl = document.getElementById('news-count');

    if (countEl) countEl.textContent = items.length;

    if (items.length === 0) {
        container.innerHTML = '<div class="news-loading">暂无快讯</div>';
        return;
    }

    let html = '';
    items.forEach(function (item) {
        const tags = (item.subjects || []).slice(0, 2);
        const tagHtml = tags.map(function (s) {
            return '<span class="nc-tag">' + escapeHtml(s.subject_name || s) + '</span>';
        }).join('');

        html += '<div class="news-card">'
            + '<div class="nc-time">' + (item.time || '') + '</div>'
            + '<div class="nc-text">' + escapeHtml(item.text) + '</div>'
            + (tagHtml ? '<div class="nc-tags">' + tagHtml + '</div>' : '')
            + '</div>';
    });

    container.innerHTML = html;
}

// ─── 自适应 ──────────────────────────────────────
function handleResize() {
    if (pieChart) pieChart.resize();
    if (timelineChart) timelineChart.resize();
    if (klineChart) klineChart.resize();
}

window.addEventListener('resize', handleResize);

// ─── 主数据请求（5秒轮询）─────────────────────────
async function fetchAll() {
    try {
        const resp = await fetch(API_BASE + '/all');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();

        updateIndices(data.indices || {});
        updateStocks(data.stocks || {});
        updatePieChart(data.market_overview || { advance: 0, decline: 0, even: 0 });
        updateNews(data.news || {});

        const timeEl = document.getElementById('update-time');
        if (timeEl) timeEl.textContent = data.update_time || '--:--:--';
    } catch (err) {
        console.error('主数据获取失败:', err);
    }
}

// ─── 分时数据请求（30秒轮询）─────────────────────
let intradayData = null;

async function fetchIntraday() {
    try {
        const resp = await fetch(API_BASE + '/intraday?code=sh000001');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        intradayData = await resp.json();

        if (intradayData && intradayData.trends && intradayData.trends.length > 0) {
            updateTimelineChart(intradayData);
        }
    } catch (err) {
        console.error('分时数据获取失败:', err);
    }
}

// ─── K线数据请求（首次加载 + 5分钟刷新）───────────
async function fetchKline() {
    try {
        const resp = await fetch(API_BASE + '/kline?code=sh000001&days=120');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const data = await resp.json();

        if (data && data.klines && data.klines.length > 0) {
            renderKlineChart(data);
        }
    } catch (err) {
        console.error('K线数据获取失败:', err);
    }
}

// ─── 启动 ────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initPieChart();
    initTimelineChart();
    initKlineChart();

    // 首次加载
    fetchAll();
    fetchIntraday();
    fetchKline();

    // 定时刷新
    setInterval(fetchAll, REFRESH_MAIN);
    setInterval(fetchIntraday, REFRESH_INTRADAY);
    setInterval(fetchKline, REFRESH_KLINE);
});

// ══════════════════════════════════════════════════════
// 自选股管理
// ══════════════════════════════════════════════════════

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
        const resp = await fetch(API_BASE + '/watchlist');
        const data = await resp.json();
        const list = data.stocks || [];
        document.getElementById('manage-count').textContent = list.length;
        const container = document.getElementById('manage-list');
        container.innerHTML = list.map(function (s) {
            return '<div class="manage-item">'
                + '<div><span class="mi-name">' + escapeHtml(s.name) + '</span>'
                + '<span class="mi-code">' + s.code + '</span></div>'
                + '<button class="btn-remove" onclick="removeStock(\'' + s.code + '\')">删除</button>'
                + '</div>';
        }).join('');
    } catch (err) {
        console.error('加载自选股失败:', err);
    }
}

async function addStock() {
    const exchange = document.getElementById('add-exchange').value;
    const codeRaw = document.getElementById('add-code').value.trim();
    const name = document.getElementById('add-name').value.trim();
    const resultEl = document.getElementById('add-result');

    if (!codeRaw || codeRaw.length !== 6 || !/^\d{6}$/.test(codeRaw)) {
        resultEl.textContent = '请输入6位数字股票代码';
        resultEl.className = 'add-result error';
        return;
    }
    if (!name) {
        resultEl.textContent = '请输入股票名称';
        resultEl.className = 'add-result error';
        return;
    }

    const code = exchange + codeRaw;

    try {
        const resp = await fetch(API_BASE + '/watchlist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, name: name }),
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || 'HTTP ' + resp.status);
        }

        const result = await resp.json();
        resultEl.textContent = '已添加 ' + name + ' (' + result.count + '只)';
        resultEl.className = 'add-result success';
        document.getElementById('add-code').value = '';
        document.getElementById('add-name').value = '';
        loadManageList();
    } catch (err) {
        resultEl.textContent = err.message;
        resultEl.className = 'add-result error';
    }
}

async function removeStock(code) {
    try {
        const resp = await fetch(API_BASE + '/watchlist/' + code, { method: 'DELETE' });
        if (!resp.ok) throw new Error('删除失败');
        loadManageList();
    } catch (err) {
        console.error('删除失败:', err);
    }
}
