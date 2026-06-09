# A股大屏 📊

> 用闲置机顶盒 + Armbian + HDMI 打造全屏A股实时行情看板

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 简介

将刷入 Armbian 的闲置机顶盒（aarch64/S905L）改造成全屏显示的 A 股实时行情看板。连接 HDMI 电视即可变身专业炒股大屏，支持实时指数、自选股、分时走势、K 线、涨跌分布、财联社快讯等。

极致轻量——787MB 内存 + 512MB swap 即可稳定运行。

## 功能

- 📊 **六大指数**：上证 / 深证 / 创业板 / 科创50 / 北证50 / 纽约金主连
- 📋 **自选股管理**：网页添加/删除，持久化保存（默认12只权重股）
- 📈 **分时走势图**：腾讯财经实时分时数据，精确到每分钟
- 📉 **日K线图**：东方财富K线数据，MA5/MA10/MA20 均线 + 成交量
- 🥧 **涨跌家数饼图**：乐咕乐股网全市场涨跌家数对比
- 📰 **实时快讯**：财联社电报纵列卡片，自动滚动更新
- 🔄 **自动刷新**：每 5 秒拉取最新行情
- 🖥️ **HDMI 全屏显示**：surf 浏览器 + Mali GPU 加速，支持开机自启
- 🎨 **赛博朋克暗色主题**：红涨绿跌，大字适配电视频距
- 🔧 **零依赖构建**：纯 HTML/CSS/JS + Python FastAPI

## 架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│  HDMI 电视    │     │  Nginx(:8081) │     │  FastAPI(:5000)   │
│  surf 全屏    │────▶│  (反向代理)   │────▶│  (数据清洗/5秒缓存)│
└──────────────┘     └──────────────┘     └────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────┐
                    │          数据源                │                   │
                    ├───────────────────────────────┼───────────────────┤
                    │  新浪财经 hq.sinajs.cn         │  指数/个股行情     │
                    │  腾讯财经 web.ifzq.gtimg.cn    │  分时数据          │
                    │  东方财富 push2his             │  日K线数据         │
                    │  乐咕乐股 legulegu.com         │  涨跌家数          │
                    │  财联社 cls.cn                 │  实时电报快讯      │
                    └───────────────────────────────┴───────────────────┘
```

## 快速部署

### 前提条件

- Armbian 系统（aarch64/ARM64）
- Python 3.11+
- Nginx（可选，用于反向代理）
- HDMI 电视/显示器（全屏显示需要）

### 安装

```bash
# 克隆仓库
git clone https://github.com/quick220/agushare.git
cd agushare

# 安装 Python 依赖
pip install -r backend/requirements.txt

# 启动后端
cd backend
python3 -m uvicorn app:app --host 0.0.0.0 --port 5000 &

# （可选）配置 Nginx 反向代理
# nginx/default.conf → /etc/nginx/sites-enabled/agushare
cp ../nginx/default.conf /etc/nginx/sites-enabled/agushare
systemctl restart nginx
```

打开浏览器访问 `http://<IP>:8081` 即可。

### 一键部署脚本

```bash
bash deploy/setup.sh
```

## HDMI 电视全屏显示

将机顶盒通过 HDMI 连接到电视，安装 surf 浏览器和 Xorg：

```bash
apt install xorg surf xdotool
```

然后运行：

```bash
# 启动一次
bash deploy/kiosk.sh

# 安装为开机自启服务
bash deploy/kiosk.sh --install
```

服务重启后电视自动显示看板。脚本包含：
- surf 浏览器全屏显示（1920×1080）
- Mali GPU 加速（lima 驱动）
- 防休眠：每 55 秒微移鼠标

## 默认自选股

| 代码 | 名称 | 市场 |
|------|------|------|
| sh600519 | 贵州茅台 | 上海 |
| sh601318 | 中国平安 | 上海 |
| sh600036 | 招商银行 | 上海 |
| sh600900 | 长江电力 | 上海 |
| sz000333 | 美的集团 | 深圳 |
| sz002415 | 海康威视 | 深圳 |
| sz002594 | 比亚迪 | 深圳 |
| sz300750 | 宁德时代 | 深圳 |
| sz000858 | 五粮液 | 深圳 |
| sz002475 | 立讯精密 | 深圳 |
| sz000001 | 平安银行 | 深圳 |
| sz002714 | 牧原股份 | 深圳 |

## 默认指数

| 代码 | 名称 | 数据源 |
|------|------|--------|
| sh000001 | 上证指数 | 新浪财经 |
| sz399001 | 深证成指 | 新浪财经 |
| sz399006 | 创业板指 | 新浪财经 |
| sh000688 | 科创50 | 新浪财经 |
| bj899050 | 北证50 | 新浪财经 |
| hf_GC | 纽约金主连 | 新浪国际期货 |

## 布局

三栏布局，适合宽屏电视：

| 左栏 (260px) | 中栏 (1fr) | 右栏 (1.3fr) |
|:---|:---|:---|
| 财联社快讯纵列 | 指数卡片 (2行3列) | 分时走势图 |
| | 自选股列表 | 日K线图 |
| | | 涨跌分布饼图 |

## 数据源说明

| 数据 | 接口 | 说明 |
|------|------|------|
| A股指数/个股行情 | `hq.sinajs.cn/list=<codes>` | 新浪免费行情，UTF-8编码 |
| 国际期货行情 | `hq.sinajs.cn/list=<hf_code>` | 新浪国际期货，`hf_GC`=纽约金 |
| 分时走势 | `web.ifzq.gtimg.cn/appstock/app/minute/query` | 腾讯财经，精确到每分钟 |
| 日K线 | `push2his.eastmoney.com/api/qt/stock/kline/get` | 东方财富，120日K线 |
| 涨跌家数 | `legulegu.com/stockdata/market-activity` | 乐咕乐股，全市场涨跌统计 |
| 电报快讯 | `cls.cn/api/telegraph` | 财联社，实时滚动新闻 |

## 项目结构

```
agushare/
├── README.md
├── LICENSE
├── .gitignore
├── backend/
│   ├── app.py               ← FastAPI 后端（数据采集/缓存/API路由）
│   ├── requirements.txt     ← Python 依赖
│   └── Dockerfile           ← 容器构建（备选，当前使用宿主Python）
├── frontend/
│   ├── index.html           ← 大屏三栏布局 + 管理弹窗
│   ├── css/style.css        ← 赛博朋克暗色主题
│   └── js/app.js            ← 行情渲染 + ECharts图表 + 自选股管理
├── nginx/
│   └── default.conf         ← 反向代理配置（端口8081）
├── deploy/
│   ├── setup.sh             ← 一键部署脚本
│   ├── kiosk.sh             ← HDMI全屏启动脚本（surf + Xorg）
│   └── agushare-kiosk.service ← 开机自启 systemd 服务
└── docker-compose.yml       ← Podman编排（备选）
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端 | 纯 HTML/CSS/JS + ECharts | 无需构建工具，轻量加载 |
| 后端 | Python FastAPI + httpx | 异步非阻塞，5秒内存缓存 |
| Web 服务 | Nginx (Alpine) | 反向代理 + Gzip |
| 图表 | Apache ECharts 5.5 | 分时曲线 + K线蜡烛图 + 饼图 |
| 显示 | surf (WebKit) + Xorg | 轻量全屏浏览器，1920×1080 |
| GPU | Mali lima 开源驱动 | S905L 盒子 GPU 加速 |
| 防休眠 | xdotool 鼠标微移 | 每55秒防止屏幕关闭 |
| 部署 | systemd + Podman | 开机自启，容器可选 |

## 自定义配置

- **自选股**：修改 `backend/app.py` 中的 `_watchlist` 字典，或通过网页管理界面操作
- **指数列表**：修改 `backend/app.py` 中的 `INDEX_CODES` 字典
- **刷新频率**：修改 `backend/app.py` 中的 `CACHE_SECONDS`（默认5秒）
- **服务端口**：修改 `nginx/default.conf` 和 `deploy/kiosk.sh` 中的端口

## 已知问题

- 东方财富 `push2his` 接口在部分网络环境下 IPv6 断连，已强制 IPv4 解析
- 乐咕乐股网偶发 504 网关超时，后端 5 秒超时降级
- 787MB 内存高度紧张，GPU 加速与 WebKit 渲染需平衡内存占用

## License

MIT
