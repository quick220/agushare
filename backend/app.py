"""
A股大屏 - 后端数据代理服务
从新浪财经免费API获取A股实时行情，提供缓存、CORS、自选股管理
"""

import os
import json
import time
import re
import asyncio
import logging
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ─── 日志 ────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agushare")

# ─── 应用 ────────────────────────────────────────────
app = FastAPI(title="A股大屏 Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 配置 ────────────────────────────────────────────
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "5"))
STOCKS_FILE = os.environ.get("STOCKS_FILE", "/data/stocks.json")

# ─── 三大指数代码 ────────────────────────────────────
INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
}

# ─── 默认自选股（首次启动时写入） ──────────────────────
DEFAULT_STOCKS = {
    "sh600519": "贵州茅台",
    "sh601318": "中国平安",
    "sh600036": "招商银行",
    "sh600900": "长江电力",
    "sz000333": "美的集团",
    "sz002415": "海康威视",
    "sz002594": "比亚迪",
    "sz300750": "宁德时代",
    "sz000858": "五粮液",
    "sz002475": "立讯精密",
    "sz000001": "平安银行",
    "sz002714": "牧原股份",
}

# ─── 持久化自选股管理 ────────────────────────────────
_watchlist: Dict[str, str] = {}  # code -> name


def _load_watchlist():
    """从文件加载自选股列表"""
    global _watchlist
    try:
        if os.path.exists(STOCKS_FILE):
            with open(STOCKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    _watchlist = data
                    log.info(f"已加载 {len(_watchlist)} 只自选股")
                    return
        log.info("无自选股文件，使用默认列表")
    except Exception as e:
        log.warning(f"加载自选股文件失败: {e}")

    _watchlist = dict(DEFAULT_STOCKS)
    _save_watchlist()


def _save_watchlist():
    """保存自选股列表到文件"""
    try:
        os.makedirs(os.path.dirname(STOCKS_FILE) or ".", exist_ok=True)
        with open(STOCKS_FILE, "w", encoding="utf-8") as f:
            json.dump(_watchlist, f, ensure_ascii=False, indent=2)
        log.info(f"已保存 {len(_watchlist)} 只自选股")
    except Exception as e:
        log.error(f"保存自选股失败: {e}")


# 启动时加载
_load_watchlist()


def _validate_stock_code(code: str) -> bool:
    """验证股票代码格式：sh/sz + 6位数字"""
    return bool(re.match(r"^(sh|sz)\d{6}$", code))


# ─── 缓存 ────────────────────────────────────────────
_cache: Dict[str, tuple] = {}  # key -> (timestamp, data)


def _get_cached(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < CACHE_SECONDS:
        return entry[1]
    return None


def _set_cache(key: str, data):
    _cache[key] = (time.time(), data)


# ─── 新浪财经 API ─────────────────────────────────────
def _parse_sina_response(data: str) -> Optional[Dict]:
    """解析新浪财经返回的股票行情数据"""
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
        "change_pct": 0,
        "change_amount": 0,
    }


def _compute_change(data: dict) -> dict:
    prev = data.get("prev_close", 1)
    price = data.get("price", 0)
    if prev and prev > 0:
        data["change_amount"] = round(price - prev, 2)
        data["change_pct"] = round((price - prev) / prev * 100, 2)
    else:
        data["change_amount"] = 0
        data["change_pct"] = 0
    return data


async def _fetch_sina(codes: list) -> Dict[str, dict]:
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
    lines = raw.strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        parsed = _parse_sina_response(line)
        if parsed is None:
            continue
        parsed = _compute_change(parsed)
        m = re.search(r'hq_str_([^=]+)="', line)
        code = m.group(1) if m else "unknown"
        result[code] = parsed
    return result


# ═══════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════


@app.get("/health")
async def health():
    return {"status": "ok", "cache_seconds": CACHE_SECONDS, "watchlist_count": len(_watchlist)}


# ─── 自选股管理 ──────────────────────────────────────


@app.get("/api/watchlist")
async def get_watchlist():
    """获取自选股列表"""
    return JSONResponse(content={
        "stocks": [{"code": k, "name": v} for k, v in _watchlist.items()],
        "count": len(_watchlist),
    })


class AddStockRequest(BaseModel):
    code: str
    name: str


@app.post("/api/watchlist/add")
async def add_stock(req: AddStockRequest):
    """添加自选股"""
    code = req.code.strip()
    name = req.name.strip()

    if not _validate_stock_code(code):
        raise HTTPException(status_code=400, detail=f"无效的股票代码格式: {code}，应为 shXXXXXX 或 szXXXXXX")

    if not name:
        raise HTTPException(status_code=400, detail="股票名称不能为空")

    if code in _watchlist:
        raise HTTPException(status_code=409, detail=f"股票 {code} ({_watchlist[code]}) 已在自选股中")

    # 验证该代码是否有行情数据
    data = await _fetch_sina([code])
    if code not in data or data[code].get("price", 0) == 0:
        # 允许添加，但给出警告
        log.warning(f"股票 {code} ({name}) 可能无行情数据")

    _watchlist[code] = name
    _save_watchlist()
    # 清除股票相关缓存
    for k in list(_cache.keys()):
        if k in ("stocks", "all", "market_overview"):
            del _cache[k]

    return {"success": True, "code": code, "name": name, "count": len(_watchlist)}


@app.delete("/api/watchlist/{code:path}")
async def remove_stock(code: str):
    """删除自选股"""
    code = code.strip()
    if code not in _watchlist:
        raise HTTPException(status_code=404, detail=f"股票 {code} 不在自选股中")

    name = _watchlist.pop(code)
    _save_watchlist()
    # 清除缓存
    for k in list(_cache.keys()):
        if k in ("stocks", "all", "market_overview"):
            del _cache[k]

    return {"success": True, "removed": code, "name": name, "count": len(_watchlist)}


# ─── 行情数据 ────────────────────────────────────────


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
            d["amount"] = round(d.get("amount", 0) / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "amount": 0}

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

    codes = list(_watchlist.keys())
    data = await _fetch_sina(codes)

    result = {}
    for code, name in _watchlist.items():
        if code in data:
            d = data[code]
            d["name"] = name
            d["amount"] = round(d.get("amount", 0) / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0,
                            "change_amount": 0, "volume": 0, "amount": 0, "turnover": "0.00%"}

    _set_cache(cache_key, result)
    return JSONResponse(content=result)


@app.get("/api/market-overview")
async def get_market_overview():
    """获取市场涨跌家数概览"""
    cache_key = "market_overview"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    stocks_data = await _fetch_sina(list(_watchlist.keys()))
    advance = decline = even = 0
    for d in stocks_data.values():
        pct = d.get("change_pct", 0)
        if pct > 0:
            advance += 1
        elif pct < 0:
            decline += 1
        else:
            even += 1

    result = {"advance": advance, "decline": decline, "even": even,
              "total": advance + decline + even}
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
        "watchlist_count": len(_watchlist),
        "update_time": time.strftime("%H:%M:%S"),
        "cache_seconds": CACHE_SECONDS,
    }
    _set_cache(cache_key, result)
    return JSONResponse(content=result)


# ─── 内部辅助 ────────────────────────────────────────


async def _get_indices_data() -> dict:
    codes = list(INDEX_CODES.keys())
    data = await _fetch_sina(codes)
    result = {}
    for code, name in INDEX_CODES.items():
        if code in data:
            d = data[code]
            d["name"] = name
            d["amount"] = round(d.get("amount", 0) / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0, "change_amount": 0, "amount": 0}
    is_open = any(d.get("volume", 0) > 0 for d in data.values()) if data else False
    result["_market_status"] = "open" if is_open else "closed"
    return result


async def _get_stocks_data() -> dict:
    codes = list(_watchlist.keys())
    data = await _fetch_sina(codes)
    result = {}
    for code, name in _watchlist.items():
        if code in data:
            d = data[code]
            d["name"] = name
            d["amount"] = round(d.get("amount", 0) / 10000, 2)
            result[code] = d
        else:
            result[code] = {"name": name, "price": 0, "change_pct": 0,
                            "change_amount": 0, "volume": 0, "amount": 0, "turnover": "0.00%"}
    return result


async def _get_market_overview_data() -> dict:
    stocks_data = await _fetch_sina(list(_watchlist.keys()))
    advance = decline = even = 0
    for d in stocks_data.values():
        pct = d.get("change_pct", 0)
        if pct > 0:
            advance += 1
        elif pct < 0:
            decline += 1
        else:
            even += 1
    return {"advance": advance, "decline": decline, "even": even,
            "total": advance + decline + even}
