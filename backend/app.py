"""
A股大屏 - 后端数据代理服务
从新浪财经免费API获取A股实时行情，提供缓存和CORS支持
"""

import os
import time
import re
import asyncio
import logging
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ─── 日志 ────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agushare")

# ─── 应用 ────────────────────────────────────────────
app = FastAPI(title="A股大屏 Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 配置 ────────────────────────────────────────────
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "5"))

# ─── 自选股列表 ──────────────────────────────────────
# 格式：代码 -> 名称
# sh=上海, sz=深圳, 代码为6位数字
STOCK_LIST: Dict[str, str] = {
    # 权重蓝筹
    "sh600519": "贵州茅台",
    "sh601318": "中国平安",
    "sh600036": "招商银行",
    "sh600900": "长江电力",
    "sh601166": "兴业银行",
    "sh600887": "伊利股份",
    "sh601398": "工商银行",
    "sh600276": "恒瑞医药",
    # 深圳权重
    "sz000333": "美的集团",
    "sz002415": "海康威视",
    "sz000858": "五粮液",
    "sz002594": "比亚迪",
    "sz300750": "宁德时代",
    "sz002475": "立讯精密",
    "sz002714": "牧原股份",
    "sz000001": "平安银行",
}

# ─── 缓存 ────────────────────────────────────────────
_cache: Dict[str, tuple] = {}  # key -> (timestamp, data)


def _get_cached(key: str):
    """获取缓存，过期返回 None"""
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < CACHE_SECONDS:
        return entry[1]
    return None


def _set_cache(key: str, data):
    _cache[key] = (time.time(), data)


# ─── 新浪财经 API ─────────────────────────────────────

# 三大指数代码
INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
}

# 涨跌家数（深证）
AD_DECLINE_CODE = "sz399107"


def _parse_sina_response(data: str) -> Optional[Dict]:
    """
    解析新浪财经返回的股票行情数据
    格式: var hq_str_sh600519="贵州茅台,1842.00,1840.50,...";
    """
    m = re.search(r'hq_str_[^=]+="([^"]*)"', data)
    if not m:
        return None
    fields = m.group(1).split(",")
    if len(fields) < 32:
        return None
    return {
        "name": fields[0],
        "open": float(fields[1]) if fields[1] else 0,
        "prev_close": float(fields[2]) if fields[2] else 0,
        "price": float(fields[3]) if fields[3] else 0,
        "high": float(fields[4]) if fields[4] else 0,
        "low": float(fields[5]) if fields[5] else 0,
        "volume": int(fields[8]) if fields[8] else 0,  # 成交量（手）
        "amount": float(fields[9]) if fields[9] else 0,  # 成交额（万元）
        "turnover": fields[10] if len(fields) > 10 else "0.00%",  # 换手率
        "change_pct": 0,  # 将在下面计算
        "change_amount": 0,
    }


def _compute_change(data: dict) -> dict:
    """计算涨跌幅和涨跌额"""
    prev = data.get("prev_close", 1)
    price = data.get("price", 0)
    if prev and prev > 0:
        data["change_amount"] = round(price - prev, 2)
        data["change_pct"] = round((price - prev) / prev * 100, 2)
    else:
        data["change_amount"] = 0
        data["change_pct"] = 0
    return data


async def _fetch_sina(codes: List[str]) -> Dict[str, dict]:
    """批量获取新浪行情"""
    if not codes:
        return {}
    url = f"https://hq.sinajs.cn/list={','.join(codes)}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        try:
            resp = await client.get(url)
            resp.encoding = "gbk"
            raw = resp.text
        except Exception as e:
            log.error(f"请求新浪API失败: {e}")
            return {}

    result = {}
    # 按行分割解析每只股票
    lines = raw.strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        parsed = _parse_sina_response(line)
        if parsed is None:
            continue
        parsed = _compute_change(parsed)
        # 从行中找到对应的代码
        m = re.search(r'hq_str_([^=]+)="', line)
        code = m.group(1) if m else "unknown"
        result[code] = parsed
    return result


# ─── API 端点 ────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "cache_seconds": CACHE_SECONDS}


@app.get("/api/indices")
async def get_indices():
    """获取三大指数实时行情"""
    cache_key = "indices"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    codes = list(INDEX_CODES.keys())
    data = await _fetch_sina(codes)

    result = {}
    for code, name in INDEX_CODES.items():
        if code in data:
            d = data[code]
            d["name"] = name
            # 指数成交额单位是亿元
            if "amount" in d:
                d["amount"] = round(d["amount"] / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "amount": 0}

    # 成交量已为0 -> 休市
    is_open = any(d.get("volume", 0) > 0 for d in data.values()) if data else False
    result["_market_status"] = "open" if is_open else "closed"

    _set_cache(cache_key, result)
    return JSONResponse(content=result)


@app.get("/api/stocks")
async def get_stocks():
    """获取自选股行情"""
    cache_key = "stocks"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    codes = list(STOCK_LIST.keys())
    data = await _fetch_sina(codes)

    result = {}
    for code, name in STOCK_LIST.items():
        if code in data:
            d = data[code]
            d["name"] = name
            # 成交额: 万元 -> 亿元
            if "amount" in d:
                d["amount"] = round(d["amount"] / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "volume": 0, "amount": 0, "turnover": "0.00%"}

    _set_cache(cache_key, result)
    return JSONResponse(content=result)


@app.get("/api/market-overview")
async def get_market_overview():
    """
    获取市场涨跌家数概览
    使用深证涨跌家数指标
    """
    cache_key = "market_overview"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    data = await _fetch_sina([AD_DECLINE_CODE])

    result = {"advance": 0, "decline": 0, "even": 0}
    if AD_DECLINE_CODE in data:
        d = data[AD_DECLINE_CODE]
        # 涨跌家数在某些字段中
        # 字段格式可能不同，尝试从原始数据中提取
        pass

    # 备用方案：从自选股中统计涨跌
    stocks_data = await _fetch_sina(list(STOCK_LIST.keys()))
    advance = decline = even = 0
    for code, d in stocks_data.items():
        pct = d.get("change_pct", 0)
        if pct > 0:
            advance += 1
        elif pct < 0:
            decline += 1
        else:
            even += 1

    result = {"advance": advance, "decline": decline, "even": even, "total": advance + decline + even}
    _set_cache(cache_key, result)
    return JSONResponse(content=result)


@app.get("/api/all")
async def get_all():
    """一次获取所有数据（前端主要调用点）"""
    cache_key = "all"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    indices, stocks, overview = await asyncio.gather(
        _get_indices_data(),
        _get_stocks_data(),
        _get_market_overview_data(),
    )

    result = {
        "indices": indices,
        "stocks": stocks,
        "market_overview": overview,
        "update_time": time.strftime("%H:%M:%S"),
        "cache_seconds": CACHE_SECONDS,
    }
    _set_cache(cache_key, result)
    return JSONResponse(content=result)


# ─── 内部辅助方法 ────────────────────────────────────


async def _get_indices_data() -> dict:
    codes = list(INDEX_CODES.keys())
    data = await _fetch_sina(codes)
    result = {}
    for code, name in INDEX_CODES.items():
        if code in data:
            d = data[code]
            d["name"] = name
            if "amount" in d:
                d["amount"] = round(d["amount"] / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "amount": 0}
    is_open = any(d.get("volume", 0) > 0 for d in data.values()) if data else False
    result["_market_status"] = "open" if is_open else "closed"
    return result


async def _get_stocks_data() -> dict:
    codes = list(STOCK_LIST.keys())
    data = await _fetch_sina(codes)
    result = {}
    for code, name in STOCK_LIST.items():
        if code in data:
            d = data[code]
            d["name"] = name
            if "amount" in d:
                d["amount"] = round(d["amount"] / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "volume": 0, "amount": 0, "turnover": "0.00%"}
    return result


async def _get_market_overview_data() -> dict:
    stocks_data = await _fetch_sina(list(STOCK_LIST.keys()))
    advance = decline = even = 0
    for d in stocks_data.values():
        pct = d.get("change_pct", 0)
        if pct > 0:
            advance += 1
        elif pct < 0:
            decline += 1
        else:
            even += 1
    return {"advance": advance, "decline": decline, "even": even, "total": advance + decline + even}
