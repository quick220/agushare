# A股大屏 📊

> 用闲置机顶盒 + Armbian + Podman 打造 A股实时行情大屏看板

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 简介

将刷入 Armbian 的闲置机顶盒（aarch64）改造成全屏显示的 A股实时行情大屏看板。所有服务通过 Podman 隔离部署，极致轻量，适合低配 ARM 设备。

## 功能

- 📈 **三大指数**：上证、深成、创业板实时点数、涨跌幅、成交额
- 📋 **自选股列表**：名称、现价、涨跌幅、换手率，支持自定义
- 🥧 **涨跌家数对比**：ECharts 饼图直观展示
- 🔄 **自动刷新**：每 5 秒拉取最新行情
- 🎨 **赛博朋克深色科技风**：适合大屏远距离观看
- 🐳 **Podman 部署**：Rootless 模式，极致资源节约

## 架构

```
┌─────────┐     ┌─────────────┐     ┌───────────────┐
│ 浏览器  │────▶│  Nginx (:8080)│────▶│  FastAPI (:5000)│
│ (电视)  │     │  (反向代理)  │     │  (数据清洗/缓存)│
└─────────┘     └─────────────┘     └───────┬───────┘
                                            │
                                    ┌───────▼───────┐
                                    │  新浪财经 API  │
                                    │ (hq.sinajs.cn) │
                                    └───────────────┘
```

## 快速启动

### 前提条件

- Armbian 系统（aarch64/ARM64）
- 已安装 Podman 和 podman-compose

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
# 启动所有服务
podman-compose up -d

# 查看日志
podman-compose logs -f

# 停止服务
podman-compose down
```

打开浏览器访问 `http://<机顶盒IP>:8080` 即可。

## 自定义自选股

编辑 `backend/app.py` 中的 `STOCK_LIST` 变量，按格式 `市场.代码` 添加或移除股票：

```python
STOCK_LIST = {
    "sh600519": "贵州茅台",
    "sz000858": "五粮液",
    # ...
}
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 前端 | 纯 HTML/CSS/JS + ECharts |
| 后端 | Python FastAPI |
| Web 服务 | Nginx (Alpine) |
| 容器 | Podman + podman-compose |
| 数据源 | 新浪财经免费 API |
| 图表 | Apache ECharts |

## License

MIT
