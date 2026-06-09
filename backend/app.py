"""
A股大屏 - 后端数据代理服务
从新浪财经免费API获取A股实时行情，提供缓存、CORS、自选股管理
"""

import os
import json
import time
import re
import asyncio
import socket
import logging
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


# ─── IPv4 辅助（armcube 上东方财富 API 的 IPv6 连接不稳定）───────
_EM_HOST = "push2his.eastmoney.com"
_EM_IPV4 = None  # lazy resolve


def _resolve_em_ipv4() -> str:
    """解析东方财富域名到 IPv4 地址（缓存结果）"""
    global _EM_IPV4
    if _EM_IPV4 is None:
        try:
            addrs = socket.getaddrinfo(_EM_HOST, 80, socket.AF_INET)
            _EM_IPV4 = addrs[0][4][0]
            log.info(f"东方财富 API 已解析到 IPv4: {_EM_IPV4}")
        except Exception as e:
            log.warning(f"解析东方财富域名失败: {e}")
            _EM_IPV4 = _EM_HOST  # fallback 到域名
    return _EM_IPV4

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

# ─── 指数代码（前三大指数 + 科创/北交/黄金）───────────
INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "bj899050": "北证50",
    "sh518880": "黄金ETF",
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


# ─── 东方财富 API ───────────────────────────────────
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}


def _to_secid(code: str) -> Optional[str]:
    """转换 sh/sz 代码为东方财富 secid 格式 (sh→1., sz→0.)"""
    if len(code) < 8:
        return None
    market = code[:2]
    raw = code[2:]
    if not raw.isdigit():
        return None
    if market == 'sh':
        return f'1.{raw}'
    elif market == 'sz':
        return f'0.{raw}'
    return None


async def _fetch_em_intraday(code: str, retries: int = 2) -> Optional[dict]:
    """从东方财富获取指数/个股分时数据"""
    secid = _to_secid(code)
    if not secid:
        return None
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "ndays": "1",
        "iscr": "0",
    }
    ip = _resolve_em_ipv4()
    url = f"http://{ip}/api/qt/stock/trends2/get"
    headers = {**EM_HEADERS, "Host": _EM_HOST}

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), headers=headers) as client:
                resp = await client.get(url, params=params)
                raw = resp.json()
                d = raw.get("data", {})
                trends_raw = d.get("trends", [])
                trends = []
                for t in trends_raw:
                    parts = t.split(",")
                    if len(parts) >= 8:
                        try:
                            # 格式: time,open,close,high,low,volume,amount,avg_price
                            trends.append({
                                "time": parts[0],
                                "price": float(parts[2]) if parts[2] else 0,
                                "high": float(parts[3]) if parts[3] else 0,
                                "low": float(parts[4]) if parts[4] else 0,
                                "volume": float(parts[5]) if parts[5] else 0,
                                "amount": float(parts[6]) if parts[6] else 0,
                            })
                        except (ValueError, IndexError):
                            continue
                if trends:
                    return {
                        "code": code,
                        "name": d.get("name", ""),
                        "prePrice": d.get("prePrice", 0),
                        "trends": trends,
                        "count": len(trends),
                    }
                log.warning(f"东方财富分时返回空 [{code}] (attempt {attempt + 1})")
        except Exception as e:
            log.warning(f"东方财富分时失败 [{code}] (attempt {attempt + 1}): {e}")
            if attempt < retries:
                await asyncio.sleep(0.5)
    return None


async def _fetch_em_kline(code: str, days: int = 120) -> Optional[dict]:
    """从东方财富获取日K线数据"""
    secid = _to_secid(code)
    if not secid:
        return None
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "end": "20500101",
        "lmt": str(days),
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
    }
    ip = _resolve_em_ipv4()
    url = f"http://{ip}/api/qt/stock/kline/get"
    headers = {**EM_HEADERS, "Host": _EM_HOST}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), headers=headers) as client:
                resp = await client.get(url, params=params)
                raw = resp.json()
                d = raw.get("data", {})
                klines_raw = d.get("klines", [])
                klines = []
                for k in klines_raw:
                    parts = k.split(",")
                    if len(parts) >= 11:
                        try:
                            klines.append({
                                "date": parts[0],
                                "open": float(parts[1]),
                                "close": float(parts[2]),
                                "high": float(parts[3]),
                                "low": float(parts[4]),
                                "volume": float(parts[5]),
                                "amount": float(parts[6]),
                                "amplitude": float(parts[7]),
                                "pct": float(parts[8]),
                                "change": float(parts[9]),
                                "turnover": float(parts[10]),
                            })
                        except (ValueError, IndexError):
                            continue
                if klines:
                    return {
                        "code": code,
                        "name": d.get("name", ""),
                        "klines": klines,
                        "count": len(klines),
                    }
                log.warning(f"东方财富K线返回空 [{code}] (attempt {attempt + 1})")
        except Exception as e:
            log.warning(f"东方财富K线失败 [{code}] (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(0.5)
    return None


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

    indices, stocks, overview, news = await asyncio.gather(
        _get_indices_data(),
        _get_stocks_data(),
        _get_market_overview_data(),
        _fetch_cls_news(),
    )

    result = {
        "indices": indices,
        "stocks": stocks,
        "market_overview": overview,
        "news": news,
        "watchlist_count": len(_watchlist),
        "update_time": time.strftime("%H:%M:%S"),
        "cache_seconds": CACHE_SECONDS,
    }
    _set_cache(cache_key, result)
    return JSONResponse(content=result)


@app.get("/api/intraday")
async def get_intraday(code: str = "sh000001"):
    """获取指数分时数据（东方财富，15秒缓存）"""
    cache_key = f"intraday_{code}"
    INTRADAY_TTL = 15

    entry = _cache.get(cache_key)
    now = time.time()

    if entry and now - entry[0] < INTRADAY_TTL:
        return JSONResponse(content=entry[1])

    data = await _fetch_em_intraday(code)
    if data:
        _cache[cache_key] = (now, data)
        return JSONResponse(content=data)

    # 获取失败但有旧数据，返回旧数据
    if entry:
        log.warning(f"分时数据刷新失败，使用{int(now - entry[0])}秒前缓存")
        return JSONResponse(content=entry[1])

    return JSONResponse(content={"code": code, "trends": [], "error": "获取分时数据失败"})


@app.get("/api/kline")
async def get_kline(code: str = "sh000001", days: int = 120):
    """获取日K线数据（东方财富，5分钟缓存）"""
    cache_key = f"kline_{code}_{days}"
    now = time.time()
    KLINE_TTL = 300

    entry = _cache.get(cache_key)
    if entry and now - entry[0] < KLINE_TTL:
        return JSONResponse(content=entry[1])

    data = await _fetch_em_kline(code, days)
    if data:
        _cache[cache_key] = (now, data)
        return JSONResponse(content=data)

    if entry:
        log.warning(f"K线刷新失败，使用{int(now - entry[0])}秒前缓存")
        return JSONResponse(content=entry[1])

    return JSONResponse(content={"code": code, "klines": [], "error": "获取K线数据失败"})


@app.get("/api/news")
async def get_news():
    """获取实时财经新闻（财联社电报）"""
    cache_key = "news"
    cached = _get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached)

    news_data = await _fetch_cls_news()
    _set_cache(cache_key, news_data)
    return JSONResponse(content=news_data)


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
    """从东方财富获取全市场涨跌家数"""
    ip = _resolve_em_ipv4()
    url = f"http://{ip}/api/qt/stock/get"
    params = {
        "secid": "1.000001",
        "fields": "f169,f170,f171",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
    }
    headers = {**EM_HEADERS, "Host": _EM_HOST}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), headers=headers) as client:
            resp = await client.get(url, params=params)
            raw = resp.json()
            d = raw.get("data", {})
            advance = d.get("f169", 0) or 0
            decline = d.get("f170", 0) or 0
            even = d.get("f171", 0) or 0
            return {"advance": advance, "decline": decline, "even": even,
                    "total": advance + decline + even}
    except Exception as e:
        log.warning(f"东方财富涨跌家数获取失败: {e}")
        return {"advance": 0, "decline": 0, "even": 0, "total": 0}


async def _fetch_cls_news() -> dict:
    """获取财联社实时电报新闻"""
    url = "https://www.cls.cn/api/cache?app=CailianpressWeb&name=telegraph&os=web&sv=8.7.9"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.cls.cn/telegraph",
    }
    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        try:
            resp = await client.get(url)
            data = resp.json()
            items = data.get("data", {}).get("roll_data", []) or data.get("data", [])
            news_list = []
            for item in items[:30]:
                title = item.get("title", "") or ""
                brief = item.get("brief", "") or ""
                content = item.get("content", "") or ""
                ctime = item.get("ctime", 0)
                subjects = item.get("subjects", [])

                # 取最佳文本
                text = title or brief or content
                if not text:
                    continue

                # 格式化时间
                from datetime import datetime
                time_str = datetime.fromtimestamp(ctime).strftime("%H:%M") if ctime else ""

                news_list.append({
                    "text": text.strip(),
                    "time": time_str,
                    "subjects": subjects if isinstance(subjects, list) else [],
                })

            return {"items": news_list, "count": len(news_list)}
        except Exception as e:
            log.error(f"获取财联社新闻失败: {e}")
            return {"items": [], "count": 0, "error": str(e)}
