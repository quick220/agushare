# A股大屏 📊

> 用闲置机顶盒 + Armbian + Podman 打造 A股实时行情大屏看板

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 简介

将刷入 Armbian 的闲置机顶盒（aarch64）改造成全屏显示的 A股实时行情大屏看板。
所有服务通过 Podman 隔离部署，极致轻量，适合低配 ARM 设备。连接 HDMI 电视即可变身专业炒股大屏。

## 功能

- 📈 **三大指数**：上证、深成、创业板实时点数、涨跌幅、成交额
- 📋 **自选股管理**：支持在网页上添加/删除关注的股票，持久化保存
- 🥧 **涨跌家数对比**：ECharts 饼图直观展示
- 📉 **上证分时走势**：实时累积分时曲线
- 🔄 **自动刷新**：每 5 秒拉取最新行情
- 🖥️ **HDMI 全屏显示**：一键驱动电视显示，支持开机自启
- 🎨 **赛博朋克深色科技风**：适合大屏远距离观看
- 🐳 **Podman 部署**：Rootless 模式，极致资源节约

## 架构

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│  HDMI 电视大屏   │     │  Nginx(:8081) │     │  FastAPI(:5000)  │
│  (Kiosk 浏览器)  │────▶│  (反向代理)   │────▶│  (数据清洗/缓存)  │
└─────────────────┘     └──────────────┘     └───────┬────────┘
                                                     │
                                             ┌───────▼────────┐
                                             │  新浪财经 API   │
                                             │ (hq.sinajs.cn)  │
                                             └────────────────┘
```

## 快速启动

### 前提条件

- Armbian 系统（aarch64/ARM64）
- 已安装 Podman 和 podman-compose
- 连接了 HDMI 电视/显示器（全屏显示需要）

### 一键部署

```bash
# 克隆仓库
git clone https://github.com/quick220/agushare.git
cd agushare

# 赋予执行权限
chmod +x deploy/setup.sh

# 一键部署
sudo ./deploy/setup.sh
```

### 手动部署

```bash
# 启动所有服务 (后台)
podman-compose up -d

# 查看日志
podman-compose logs -f

# 停止服务
podman-compose down
```

打开浏览器访问 `http://<机顶盒IP>:8081` 即可。

## HDMI 电视全屏显示

服务部署完成后，将机顶盒通过 HDMI 连接到电视，然后运行：

```bash
# 启动一次（浏览器全屏显示）
bash deploy/kiosk.sh

# 安装为系统服务（开机自启）
bash deploy/kiosk.sh --install
```

服务器重启后电视会自动显示看板。

## 管理自选股

在网页右上角点击 **⚙️** 按钮打开管理弹窗：

- **添加股票**：选择交易所（上海/深圳），输入6位代码和名称
- **删除股票**：在管理列表中点击「删除」按钮
- **自动保存**：增删操作持久化保存，重启容器不丢失

### 默认自选股

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

## 项目结构

```
agushare/
├── docker-compose.yml       ← Podman 编排 (端口 8081)
├── README.md
├── LICENSE
├── .gitignore
├── backend/
│   ├── Dockerfile            ← python:3.11-alpine (64MB)
│   ├── requirements.txt
│   └── app.py                ← FastAPI + 缓存 + CRUD
├── frontend/
│   ├── index.html            ← 大屏布局 + 管理弹窗
│   ├── css/style.css         ← 赛博朋克风格
│   └── js/app.js             ← ECharts + 自选股管理
├── nginx/
│   └── default.conf          ← 反向代理 (端口 8081)
└── deploy/
    ├── setup.sh              ← 一键部署脚本
    ├── kiosk.sh              ← 电视全屏显示脚本
    └── agushare-kiosk.service ← 开机自启 systemd 服务
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 前端 | 纯 HTML/CSS/JS + ECharts | 无需构建工具 |
| 后端 | Python FastAPI + httpx | 异步非阻塞，5秒缓存 |
| Web 服务 | Nginx (Alpine) | 反向代理 + Gzip |
| 容器 | Podman + podman-compose | Rootless，ARM64 原生 |
| 数据源 | 新浪财经免费 API | hq.sinajs.cn，无需 Key |
| 图表 | Apache ECharts 5.5 | 饼图 + 分时曲线 |
| 显示 | Chromium Kiosk 模式 | 全屏驱动 HDMI 电视 |

## 自定义配置

- **刷新频率**：修改 `docker-compose.yml` 中 `CACHE_SECONDS=5` 环境变量
- **默认自选股**：修改 `backend/app.py` 中的 `DEFAULT_STOCKS` 字典
- **服务端口**：修改 `docker-compose.yml` 和 `nginx/default.conf` 中的端口号

## License

MIT
