from __future__ import annotations

import csv
import io
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .db import connect, json_dumps, new_id, now_iso, rows_to_dicts


SOURCE_CONFIG_PATH = DATA_DIR / "sources.json"

DEFAULT_MARKET_QUOTES = [
    {"id": "CSI300", "asset_id": None, "symbol": "000300.SH", "source": "sina_simple", "sina_symbol": "s_sh000300"},
    {"id": "SP500", "asset_id": None, "symbol": "SPX", "source": "yahoo_chart", "yahoo_symbol": "^GSPC"},
    {"id": "CN10Y_BOND_ETF", "asset_id": "asset_511260", "symbol": "511260.SH", "source": "sina_simple", "sina_symbol": "s_sh511260"},
    {"id": "CORP_BOND_ETF", "asset_id": "asset_511030", "symbol": "511030.SH", "source": "sina_simple", "sina_symbol": "s_sh511030"},
    {"id": "510300.SH", "asset_id": "asset_510300", "symbol": "510300.SH", "source": "sina_simple", "sina_symbol": "s_sh510300"},
    {"id": "510880.SH", "asset_id": "asset_510880", "symbol": "510880.SH", "source": "sina_simple", "sina_symbol": "s_sh510880"},
    {"id": "159920.SZ", "asset_id": "asset_159920", "symbol": "159920.SZ", "source": "sina_simple", "sina_symbol": "s_sz159920"},
    {"id": "513180.SH", "asset_id": "asset_513180", "symbol": "513180.SH", "source": "sina_simple", "sina_symbol": "s_sh513180"},
    {"id": "512760.SH", "asset_id": "asset_512760", "symbol": "512760.SH", "source": "sina_simple", "sina_symbol": "s_sh512760"},
    {"id": "600519.SH", "asset_id": "asset_600519", "symbol": "600519.SH", "source": "sina_simple", "sina_symbol": "s_sh600519"},
    {"id": "601318.SH", "asset_id": "asset_601318", "symbol": "601318.SH", "source": "sina_simple", "sina_symbol": "s_sh601318"},
    {"id": "600036.SH", "asset_id": "asset_600036", "symbol": "600036.SH", "source": "sina_simple", "sina_symbol": "s_sh600036"},
    {"id": "300750.SZ", "asset_id": "asset_300750", "symbol": "300750.SZ", "source": "sina_simple", "sina_symbol": "s_sz300750"},
    {"id": "000333.SZ", "asset_id": "asset_000333", "symbol": "000333.SZ", "source": "sina_simple", "sina_symbol": "s_sz000333"},
    {"id": "002475.SZ", "asset_id": "asset_002475", "symbol": "002475.SZ", "source": "sina_simple", "sina_symbol": "s_sz002475"},
    {"id": "600276.SH", "asset_id": "asset_600276", "symbol": "600276.SH", "source": "sina_simple", "sina_symbol": "s_sh600276"},
    {"id": "513500.SH", "asset_id": "asset_513500", "symbol": "513500.SH", "source": "sina_simple", "sina_symbol": "s_sh513500"},
    {"id": "511010.SH", "asset_id": "asset_511010", "symbol": "511010.SH", "source": "sina_simple", "sina_symbol": "s_sh511010"},
    {"id": "511880.SH", "asset_id": "asset_511880", "symbol": "511880.SH", "source": "sina_simple", "sina_symbol": "s_sh511880"},
    {"id": "518880.SH", "asset_id": "asset_518880", "symbol": "518880.SH", "source": "sina_simple", "sina_symbol": "s_sh518880"},
    {"id": "159934.SZ", "asset_id": "asset_159934", "symbol": "159934.SZ", "source": "sina_simple", "sina_symbol": "s_sz159934"},
    {"id": "162411.SZ", "asset_id": "asset_162411", "symbol": "162411.SZ", "source": "sina_simple", "sina_symbol": "s_sz162411"},
    {"id": "159930.SZ", "asset_id": "asset_159930", "symbol": "159930.SZ", "source": "sina_simple", "sina_symbol": "s_sz159930"},
    {"id": "0700.HK", "asset_id": "asset_0700hk", "symbol": "0700.HK", "source": "sina_hk", "sina_symbol": "hk00700"},
    {"id": "9988.HK", "asset_id": "asset_9988hk", "symbol": "9988.HK", "source": "sina_hk", "sina_symbol": "hk09988"},
    {"id": "1299.HK", "asset_id": "asset_1299hk", "symbol": "1299.HK", "source": "sina_hk", "sina_symbol": "hk01299"},
    {"id": "3690.HK", "asset_id": "asset_3690hk", "symbol": "3690.HK", "source": "sina_hk", "sina_symbol": "hk03690"},
    {"id": "0005.HK", "asset_id": "asset_0005hk", "symbol": "0005.HK", "source": "sina_hk", "sina_symbol": "hk00005"},
    {"id": "2318.HK", "asset_id": "asset_2318hk", "symbol": "2318.HK", "source": "sina_hk", "sina_symbol": "hk02318"},
    {"id": "1810.HK", "asset_id": "asset_1810hk", "symbol": "1810.HK", "source": "sina_hk", "sina_symbol": "hk01810"},
    {"id": "IF_PROXY", "asset_id": "asset_ifhedge", "symbol": "IF.CFE", "source": "sina_simple", "sina_symbol": "s_sh000300"},
    {"id": "T_PROXY", "asset_id": "asset_tbond_future", "symbol": "T.CFE", "source": "sina_simple", "sina_symbol": "s_sh511260"},
    {"id": "GOLD", "asset_id": None, "symbol": "XAUUSD", "source": "yahoo_chart", "yahoo_symbol": "GC=F"},
    {"id": "GOLD_FUTURE", "asset_id": "asset_aufuture", "symbol": "GC=F", "source": "yahoo_chart", "yahoo_symbol": "GC=F"},
    {"id": "OIL", "asset_id": None, "symbol": "CL.F", "source": "yahoo_chart", "yahoo_symbol": "CL=F"},
    {"id": "OIL_FUTURE", "asset_id": "asset_oilfuture", "symbol": "CL=F", "source": "yahoo_chart", "yahoo_symbol": "CL=F"},
    {"id": "USDCNH", "asset_id": "asset_usdcnh_spot", "symbol": "USD/CNH", "source": "yahoo_chart", "yahoo_symbol": "CNH=X"},
    {"id": "EURUSD", "asset_id": "asset_eurusd", "symbol": "EUR/USD", "source": "yahoo_chart", "yahoo_symbol": "EURUSD=X"},
    {"id": "USDJPY", "asset_id": "asset_usdjpy", "symbol": "USD/JPY", "source": "yahoo_chart", "yahoo_symbol": "JPY=X"},
]

DEFAULT_RSS_FEEDS = [
    {"name": "Federal Reserve Press Releases", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "region": "美国", "category": "bond", "enabled": True, "trust": "official"},
    {"name": "EIA Today in Energy", "url": "https://www.eia.gov/rss/todayinenergy.xml", "region": "美国/全球", "category": "energy", "enabled": True, "trust": "official"},
    {"name": "CISA Cybersecurity Advisories", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "region": "美国/全球", "category": "technology", "enabled": True, "trust": "official"},
    {"name": "UN News", "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "region": "全球", "category": "geopolitics", "enabled": True, "trust": "official"},
    {"name": "SEC Press Releases", "url": "https://www.sec.gov/news/pressreleases.rss", "region": "美国", "category": "stock", "enabled": True, "trust": "official"},
    {"name": "FRED Blog", "url": "https://fredblog.stlouisfed.org/feed/", "region": "美国", "category": "macro", "enabled": True, "trust": "public_data"},
    {"name": "Yahoo Finance Market News", "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=0700.HK,9988.HK,000300.SS,^GSPC,GC=F,CL=F,CNH=X&region=US&lang=en-US", "region": "全球", "category": "market", "enabled": True, "trust": "market_media"},
]

DEFAULT_GDELT_QUERIES = [
    {"name": "Bonds Rates Credit", "query": "bond market yield curve credit spread central bank rate cut hike", "region": "全球", "category": "bond", "max_records": 4, "enabled": True},
    {"name": "Futures Commodities", "query": "futures market margin commodity volatility index futures", "region": "全球", "category": "future", "max_records": 4, "enabled": True},
    {"name": "Foreign Exchange", "query": "foreign exchange yuan dollar yen euro USD CNH currency intervention", "region": "全球", "category": "fx", "max_records": 4, "enabled": True},
    {"name": "China Hong Kong Stocks", "query": "China Hong Kong stocks earnings policy liquidity technology shares", "region": "中国大陆/香港", "category": "stock", "max_records": 4, "enabled": True},
    {"name": "Gold Safe Haven", "query": "gold safe haven real yields central bank buying geopolitical risk", "region": "全球", "category": "gold", "max_records": 4, "enabled": True},
    {"name": "Energy Oil Gas", "query": "oil gas energy OPEC inventory refinery geopolitical supply disruption", "region": "全球", "category": "energy", "max_records": 4, "enabled": True},
    {"name": "Technology AI Semiconductors", "query": "AI semiconductors export controls cybersecurity cloud chips technology regulation", "region": "全球", "category": "technology", "max_records": 4, "enabled": True},
    {"name": "Geopolitics", "query": "geopolitics Middle East Taiwan Strait Russia Ukraine sanctions trade conflict", "region": "全球", "category": "geopolitics", "max_records": 4, "enabled": True},
]

DEFAULT_WORLD_BANK_INDICATORS = [
    {"country": "CHN", "indicator": "NY.GDP.MKTP.KD.ZG", "name": "China GDP growth", "region": "中国大陆", "category": "macro", "enabled": True},
    {"country": "HKG", "indicator": "NY.GDP.MKTP.KD.ZG", "name": "Hong Kong GDP growth", "region": "香港", "category": "macro", "enabled": True},
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 SimVest/0.1 public-data-research "
        "(simulation only; low-frequency personal research)"
    ),
    "Accept": "application/json,text/csv,application/rss+xml,application/xml,text/xml,text/html;q=0.8,*/*;q=0.5",
}

POSITIVE_WORDS = {
    "support",
    "stimulus",
    "growth",
    "recovery",
    "easing",
    "cut",
    "approval",
    "buyback",
    "profit",
    "beat",
    "stable",
    "改善",
    "支持",
    "增长",
    "复苏",
    "宽松",
    "降息",
    "回购",
    "盈利",
}

NEGATIVE_WORDS = {
    "war",
    "sanction",
    "default",
    "crisis",
    "conflict",
    "tariff",
    "probe",
    "fraud",
    "loss",
    "miss",
    "tightening",
    "战争",
    "制裁",
    "违约",
    "危机",
    "冲突",
    "关税",
    "调查",
    "亏损",
    "收紧",
}

CATEGORY_KEYWORDS = {
    "bond": ["bond", "yield", "treasury", "credit", "rate", "rates", "duration", "利率", "债", "收益率", "信用"],
    "future": ["future", "futures", "margin", "derivative", "volatility", "期货", "保证金", "波动"],
    "fx": ["currency", "foreign exchange", "forex", "dollar", "yuan", "renminbi", "yen", "euro", "usd", "cnh", "汇率", "外汇", "美元", "人民币", "日元", "欧元"],
    "stock": ["stock", "equity", "shares", "earnings", "buyback", "ipo", "market", "股票", "权益", "盈利", "回购", "上市"],
    "gold": ["gold", "bullion", "safe haven", "real yield", "黄金", "避险"],
    "energy": ["oil", "gas", "energy", "opec", "crude", "inventory", "refinery", "能源", "原油", "天然气", "欧佩克", "库存"],
    "technology": ["technology", "tech", "ai", "chip", "semiconductor", "cyber", "cloud", "科技", "人工智能", "芯片", "半导体", "网络安全"],
    "geopolitics": ["war", "sanction", "conflict", "military", "taiwan", "ukraine", "middle east", "geopolitical", "战争", "制裁", "冲突", "台海", "乌克兰", "中东", "地缘"],
    "macro": ["gdp", "inflation", "cpi", "pmi", "employment", "fiscal", "monetary", "宏观", "通胀", "就业", "财政", "货币"],
}

TRUST_CONFIDENCE = {
    "official": 82,
    "public_data": 76,
    "market_media": 66,
    "gdelt": 58,
    "manual": 55,
}


@dataclass
class FetchResult:
    source: str
    records: int
    status: str
    error: str = ""


def load_source_config() -> dict[str, Any]:
    if SOURCE_CONFIG_PATH.exists():
        config = json.loads(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        config = {"enabled": True}
    return merge_default_sources(config)


def merge_default_sources(config: dict[str, Any]) -> dict[str, Any]:
    config.setdefault("enabled", True)
    config.setdefault("enable_gdelt", False)
    config.setdefault("http_timeout_seconds", 12)
    config.setdefault("min_interval_seconds", 1)
    config["market_quotes"] = merge_by_key(
        config.get("market_quotes", []),
        DEFAULT_MARKET_QUOTES,
        "id",
        replace_existing=False,
    )
    config["rss_feeds"] = merge_by_key(
        config.get("rss_feeds", []),
        DEFAULT_RSS_FEEDS,
        "name",
        replace_existing=True,
    )
    config["gdelt_queries"] = merge_by_key(
        config.get("gdelt_queries", []),
        DEFAULT_GDELT_QUERIES,
        "name",
        replace_existing=True,
    )
    config["world_bank_indicators"] = merge_by_key(
        config.get("world_bank_indicators", []),
        DEFAULT_WORLD_BANK_INDICATORS,
        "name",
        replace_existing=True,
    )
    return config


def merge_by_key(
    existing: list[dict[str, Any]],
    defaults: list[dict[str, Any]],
    key: str,
    replace_existing: bool,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in existing:
        item_key = str(item.get(key, "")).strip()
        if not item_key:
            continue
        merged[item_key] = item
        order.append(item_key)
    for item in defaults:
        item_key = str(item.get(key, "")).strip()
        if not item_key:
            continue
        if item_key not in merged:
            order.append(item_key)
            merged[item_key] = item
        elif replace_existing:
            enabled = merged[item_key].get("enabled", item.get("enabled", True))
            merged[item_key] = {**item, "enabled": enabled}
    return [merged[item_key] for item_key in order]


def save_source_config(config: dict[str, Any]) -> None:
    SOURCE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def http_get(url: str, timeout: int = 12, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={**DEFAULT_HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def safe_float(value: Any) -> float | None:
    if value in (None, "", "-", "N/A", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def sentiment_score(text: str) -> int:
    lower = text.lower()
    positive = sum(1 for word in POSITIVE_WORDS if word.lower() in lower)
    negative = sum(1 for word in NEGATIVE_WORDS if word.lower() in lower)
    if positive > negative:
        return 1
    if negative > positive:
        return -1
    return 0


def severity_score(text: str, category: str) -> int:
    lower = text.lower()
    score = 2
    if category in {"geopolitics", "policy"}:
        score += 1
    for word in ["war", "sanction", "default", "crisis", "rate", "oil", "gold", "战争", "制裁", "违约", "危机", "利率"]:
        if word in lower:
            score += 1
    return max(1, min(5, score))


def classify_category(text: str, fallback: str) -> str:
    lower = text.lower()
    best_category = fallback if fallback != "market" else "stock"
    best_hits = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword_hit(lower, keyword))
        if hits > best_hits:
            best_category = category
            best_hits = hits
    return best_category


def keyword_hit(lower_text: str, keyword: str) -> bool:
    keyword_lower = keyword.lower()
    if any("\u4e00" <= char <= "\u9fff" for char in keyword_lower):
        return keyword_lower in lower_text
    if " " in keyword_lower:
        return keyword_lower in lower_text
    return re.search(rf"(?<![a-z0-9]){re.escape(keyword_lower)}(?![a-z0-9])", lower_text) is not None


def source_confidence(source: str, trust: str | None = None) -> int:
    if trust:
        return TRUST_CONFIDENCE.get(trust, 60)
    source_lower = source.lower()
    if any(token in source_lower for token in ["federal reserve", "eia", "cisa", "un news", "sec", "world bank"]):
        return TRUST_CONFIDENCE["official"]
    if "fred" in source_lower:
        return TRUST_CONFIDENCE["public_data"]
    if "yahoo" in source_lower:
        return TRUST_CONFIDENCE["market_media"]
    if "gdelt" in source_lower:
        return TRUST_CONFIDENCE["gdelt"]
    return 60


def normalize_title(title: str) -> str:
    return " ".join((title or "").replace("\n", " ").split()).strip()


def start_source_run(conn, source: str) -> str:
    run_id = new_id("run")
    conn.execute(
        """
        INSERT INTO source_runs (id, source, started_at, finished_at, status, records, error)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, source, now_iso(), None, "running", 0, ""),
    )
    return run_id


def finish_source_run(conn, run_id: str, status: str, records: int, error: str = "") -> None:
    conn.execute(
        """
        UPDATE source_runs
        SET finished_at = ?, status = ?, records = ?, error = ?
        WHERE id = ?
        """,
        (now_iso(), status, records, error[:1000], run_id),
    )


def run_public_data_pipeline(generate_snapshot: bool = True) -> dict[str, Any]:
    config = load_source_config()
    if not config.get("enabled", False):
        return {"status": "disabled", "results": []}

    timeout = min(8, max(5, int(config.get("http_timeout_seconds", 12))))
    min_interval = min(1, max(0, int(config.get("min_interval_seconds", 1))))
    results: list[FetchResult] = []

    with connect() as conn:
        runners = [
            ("market_quotes", lambda: sync_market_quotes(conn, config, timeout)),
            ("rss_feeds", lambda: sync_rss_feeds(conn, config, timeout)),
            ("world_bank_indicators", lambda: sync_world_bank(conn, config, timeout)),
        ]
        if config.get("enable_gdelt", False):
            runners.append(("gdelt_queries", lambda: sync_gdelt(conn, config, timeout)))

        for source_name, runner in runners:
            run_id = start_source_run(conn, source_name)
            try:
                records = runner()
                finish_source_run(conn, run_id, "ok", records)
                results.append(FetchResult(source_name, records, "ok"))
            except Exception as exc:  # public sources are intentionally best-effort
                finish_source_run(conn, run_id, "error", 0, str(exc))
                results.append(FetchResult(source_name, 0, "error", str(exc)))
            time.sleep(min_interval)

        if generate_snapshot:
            snapshot_id = rebuild_market_snapshot(conn)
        else:
            snapshot_id = None

    return {
        "status": "ok",
        "snapshot_id": snapshot_id,
        "results": [result.__dict__ for result in results],
    }


def sync_market_quotes(conn, config: dict[str, Any], timeout: int) -> int:
    records = 0
    errors: list[str] = []
    quote_map: dict[str, dict[str, Any]] = {}
    for item in config.get("market_quotes", []):
        try:
            source = item.get("source")
            quote: dict[str, Any] | None = None
            if source == "eastmoney_push2":
                quote = fetch_eastmoney_quote(item, timeout)
            elif source == "sina_simple":
                quote = fetch_sina_simple(item, timeout)
            elif source == "sina_hk":
                quote = fetch_sina_hk(item, timeout)
            elif source == "stooq_csv":
                quote = fetch_stooq_quote(item, timeout)
            elif source == "yahoo_chart":
                quote = fetch_yahoo_chart(item, timeout)
            if not quote:
                continue
            upsert_market_quote(conn, item, quote)
            quote_map[item.get("id") or item.get("symbol")] = quote
            records += 1
        except Exception as exc:
            errors.append(f"{item.get('symbol') or item.get('id')}: {exc}")
            continue
    if records == 0 and errors:
        raise RuntimeError("; ".join(errors[:6]))
    if records:
        generate_market_signal_events(conn)
    return records


def fetch_eastmoney_quote(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    fields = "f43,f44,f45,f46,f57,f58,f60,f169,f170"
    params = urllib.parse.urlencode(
        {
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fltt": "2",
            "invt": "2",
            "fields": fields,
            "secid": item["secid"],
        }
    )
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
    payload = json.loads(http_get(url, timeout).decode("utf-8", errors="replace"))
    data = payload.get("data") or {}
    price = safe_float(data.get("f43"))
    prev = safe_float(data.get("f60"))
    change_pct = safe_float(data.get("f170"))
    if price is None:
        return None
    if price > 10000:
        price = price / 100.0
    if prev is not None and prev > 10000:
        prev = prev / 100.0
    if prev is None:
        prev = price
    if change_pct is None and prev:
        change_pct = (price / prev - 1) * 100
    return {
        "source": "eastmoney_push2",
        "source_url": url,
        "as_of": date.today().isoformat(),
        "symbol": item.get("symbol") or data.get("f57") or "",
        "name": data.get("f58") or item.get("symbol", ""),
        "price": price,
        "prev_close": prev,
        "day_change_pct": change_pct or 0.0,
        "ytd_return_pct": 0.0,
        "payload": data,
    }


def fetch_sina_simple(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    symbol = item["sina_symbol"]
    url = f"https://hq.sinajs.cn/list={urllib.parse.quote(symbol)}"
    raw = http_get(url, timeout, headers={"Referer": "https://finance.sina.com.cn/"})
    text = raw.decode("gb18030", errors="replace")
    values = parse_sina_values(text)
    if len(values) < 4:
        return None
    price = safe_float(values[1])
    change_pct = safe_float(values[3])
    change_value = safe_float(values[2]) or 0.0
    if price is None:
        return None
    prev = price - change_value
    if prev <= 0:
        prev = price
    return {
        "source": "sina_simple",
        "source_url": url,
        "as_of": date.today().isoformat(),
        "symbol": item.get("symbol") or symbol,
        "name": values[0],
        "price": price,
        "prev_close": prev,
        "day_change_pct": change_pct or ((price / prev - 1) * 100 if prev else 0.0),
        "ytd_return_pct": 0.0,
        "payload": {"raw": values},
    }


def fetch_sina_hk(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    symbol = item["sina_symbol"]
    url = f"https://hq.sinajs.cn/list={urllib.parse.quote(symbol)}"
    raw = http_get(url, timeout, headers={"Referer": "https://finance.sina.com.cn/"})
    text = raw.decode("gb18030", errors="replace")
    values = parse_sina_values(text)
    if len(values) < 9:
        return None
    price = safe_float(values[6])
    prev = safe_float(values[3])
    change_pct = safe_float(values[8])
    if price is None:
        return None
    if prev is None or prev <= 0:
        prev = price
    return {
        "source": "sina_hk",
        "source_url": url,
        "as_of": date.today().isoformat(),
        "symbol": item.get("symbol") or symbol,
        "name": values[1] or values[0],
        "price": price,
        "prev_close": prev,
        "day_change_pct": change_pct or ((price / prev - 1) * 100 if prev else 0.0),
        "ytd_return_pct": 0.0,
        "payload": {"raw": values},
    }


def parse_sina_values(text: str) -> list[str]:
    start = text.find('="')
    end = text.rfind('";')
    if start == -1 or end == -1 or end <= start:
        return []
    content = text[start + 2 : end]
    return [part.strip() for part in content.split(",")]


def fetch_stooq_quote(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    symbol = urllib.parse.quote(item["stooq_symbol"])
    url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
    text = http_get(url, timeout).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return None
    row = rows[0]
    close = safe_float(row.get("Close"))
    open_price = safe_float(row.get("Open")) or close
    if close is None:
        return None
    change_pct = (close / open_price - 1) * 100 if open_price else 0.0
    return {
        "source": "stooq_csv",
        "source_url": url,
        "as_of": row.get("Date") or date.today().isoformat(),
        "symbol": item.get("symbol") or item.get("stooq_symbol"),
        "name": item.get("symbol") or item.get("stooq_symbol"),
        "price": close,
        "prev_close": open_price,
        "day_change_pct": change_pct,
        "ytd_return_pct": 0.0,
        "payload": row,
    }


def fetch_yahoo_chart(item: dict[str, Any], timeout: int) -> dict[str, Any] | None:
    symbol = urllib.parse.quote(item["yahoo_symbol"], safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    payload = json.loads(http_get(url, timeout).decode("utf-8", errors="replace"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return None
    quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
    closes = [safe_float(value) for value in quote.get("close", [])]
    closes = [value for value in closes if value is not None]
    if not closes:
        return None
    price = closes[-1]
    prev = closes[-2] if len(closes) > 1 else price
    change_pct = (price / prev - 1) * 100 if prev else 0.0
    timestamp = (result.get("timestamp") or [None])[-1]
    if timestamp:
        as_of = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
    else:
        as_of = date.today().isoformat()
    meta = result.get("meta") or {}
    return {
        "source": "yahoo_chart",
        "source_url": url,
        "as_of": as_of,
        "symbol": item.get("symbol") or meta.get("symbol") or item.get("yahoo_symbol"),
        "name": meta.get("shortName") or item.get("symbol") or item.get("yahoo_symbol"),
        "price": price,
        "prev_close": prev,
        "day_change_pct": change_pct,
        "ytd_return_pct": 0.0,
        "payload": {"meta": meta, "last_close": price, "prev_close": prev},
    }


def upsert_market_quote(conn, item: dict[str, Any], quote: dict[str, Any]) -> None:
    fetched_at = now_iso()
    market_id = new_id("mkt")
    conn.execute(
        """
        INSERT INTO market_data_history (
            id, fetched_at, as_of, asset_id, symbol, source, price, prev_close,
            day_change_pct, ytd_return_pct, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            market_id,
            fetched_at,
            quote["as_of"],
            item.get("asset_id"),
            quote["symbol"],
            quote["source"],
            quote["price"],
            quote["prev_close"],
            quote["day_change_pct"],
            quote["ytd_return_pct"],
            json_dumps({"url": quote.get("source_url"), "payload": quote.get("payload", {})}),
        ),
    )

    if item.get("asset_id"):
        conn.execute(
            """
            UPDATE assets
            SET price = ?, prev_close = ?, day_change_pct = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                quote["price"],
                quote["prev_close"],
                quote["day_change_pct"],
                fetched_at,
                item["asset_id"],
            ),
        )
    elif item.get("id") in {"CSI300", "SP500"}:
        conn.execute(
            """
            UPDATE benchmarks
            SET level = ?, prev_level = ?, day_change_pct = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                quote["price"],
                quote["prev_close"],
                quote["day_change_pct"],
                fetched_at,
                item["id"],
            ),
        )


def generate_market_signal_events(conn) -> int:
    signals = [
        ("bond", "债券", ["511260.SH", "511010.SH", "511030.SH"]),
        ("future", "期货", ["IF.CFE", "T.CFE", "GC=F", "CL=F"]),
        ("fx", "外汇", ["USD/CNH", "EUR/USD", "USD/JPY"]),
        ("stock", "股票", ["000300.SH", "SPX", "0700.HK", "9988.HK", "513180.SH"]),
        ("gold", "黄金", ["XAUUSD", "518880.SH", "159934.SZ"]),
        ("energy", "能源", ["CL.F", "CL=F", "162411.SZ", "159930.SZ"]),
    ]
    records = 0
    for category, label_cn, symbols in signals:
        quote = latest_quote_for_symbols(conn, symbols)
        if not quote:
            continue
        payload = json.loads(quote.get("payload_json") or "{}")
        url = payload.get("url") or f"simvest://market-signal/{quote['symbol']}"
        change = float(quote.get("day_change_pct") or 0.0)
        direction = "上涨" if change > 0 else "下跌" if change < 0 else "持平"
        title = (
            f"{label_cn}动态：{quote['symbol']} {direction} {change:+.2f}%，"
            f"最新价 {float(quote['price']):.4f}"
        )
        if insert_raw_document(
            conn,
            source="Market Quote Signal",
            url=f"{url}#signal-{date.today().isoformat()}-{category}-{quote['symbol']}",
            title=title,
            published=quote.get("as_of") or date.today().isoformat(),
            region="全球" if category in {"fx", "gold", "energy"} else "中国大陆/香港",
            category=category,
            payload={"quote": quote, "source_payload": payload},
            trust="public_data",
        ):
            records += 1
    return records


def latest_quote_for_symbols(conn, symbols: list[str]) -> dict[str, Any] | None:
    placeholders = ",".join("?" for _ in symbols)
    row = conn.execute(
        f"""
        SELECT * FROM market_data_history
        WHERE symbol IN ({placeholders})
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        tuple(symbols),
    ).fetchone()
    return dict(row) if row else None


def sync_rss_feeds(conn, config: dict[str, Any], timeout: int) -> int:
    records = 0
    errors: list[str] = []
    for feed in config.get("rss_feeds", []):
        if not feed.get("enabled", True):
            continue
        try:
            raw = http_get(feed["url"], timeout)
            root = ET.fromstring(raw)
        except Exception as exc:
            errors.append(f"{feed.get('name', feed.get('url'))}: {exc}")
            continue
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        max_items = int(feed.get("max_items", 6))
        for node in items[:max_items]:
            title = normalize_title(text_from_xml(node, "title"))
            if not title:
                continue
            link = text_from_xml(node, "link") or node.findtext("{http://www.w3.org/2005/Atom}link")
            published = text_from_xml(node, "pubDate") or text_from_xml(node, "updated") or now_iso()
            if insert_raw_document(
                conn,
                source=feed.get("name", "rss"),
                url=link or feed["url"],
                title=title,
                published=published,
                region=feed.get("region", "全球"),
                category=feed.get("category", "news"),
                payload={"feed": feed, "title": title, "link": link},
                trust=feed.get("trust"),
            ):
                records += 1
    return records


def text_from_xml(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is not None and child.text:
        return child.text
    child = node.find(f"{{http://www.w3.org/2005/Atom}}{tag}")
    if child is not None and child.text:
        return child.text
    return ""


def sync_gdelt(conn, config: dict[str, Any], timeout: int) -> int:
    records = 0
    errors: list[str] = []
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    for query in config.get("gdelt_queries", []):
        if not query.get("enabled", True):
            continue
        try:
            params = urllib.parse.urlencode(
                {
                    "query": query["query"],
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": int(query.get("max_records", 10)),
                    "sort": "hybridrel",
                }
            )
            url = f"{base_url}?{params}"
            payload = json.loads(http_get(url, timeout).decode("utf-8", errors="replace"))
            for article in payload.get("articles", [])[: int(query.get("max_records", 10))]:
                title = normalize_title(article.get("title", ""))
                if not title:
                    continue
                if insert_raw_document(
                    conn,
                    source=f"GDELT:{query.get('name', query['query'])}",
                    url=article.get("url", url),
                    title=title,
                    published=article.get("seendate") or article.get("datetime") or now_iso(),
                    region=query.get("region", "全球"),
                    category=query.get("category", "news"),
                    payload=article,
                    trust="gdelt",
                ):
                    records += 1
            time.sleep(1)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                errors.append(f"{query.get('name')}: rate limited")
                continue
            errors.append(f"{query.get('name')}: {exc}")
        except Exception as exc:
            errors.append(f"{query.get('name')}: {exc}")
            continue
    return records


def sync_world_bank(conn, config: dict[str, Any], timeout: int) -> int:
    records = 0
    for item in config.get("world_bank_indicators", []):
        if not item.get("enabled", True):
            continue
        url = (
            "https://api.worldbank.org/v2/country/"
            f"{urllib.parse.quote(item['country'])}/indicator/{urllib.parse.quote(item['indicator'])}"
            "?format=json&per_page=5"
        )
        payload = json.loads(http_get(url, timeout).decode("utf-8", errors="replace"))
        if not isinstance(payload, list) or len(payload) < 2:
            continue
        values = [row for row in payload[1] if row.get("value") is not None]
        if not values:
            continue
        latest = values[0]
        title = f"{item['name']}: {latest.get('date')} = {latest.get('value')}"
        if insert_raw_document(
            conn,
            source="World Bank Indicators API",
            url=url,
            title=title,
            published=str(latest.get("date") or date.today().year),
            region=item.get("region", "全球"),
            category=item.get("category", "macro"),
            payload={"config": item, "latest": latest},
            trust="official",
        ):
            records += 1
    return records


def insert_raw_document(
    conn,
    source: str,
    url: str,
    title: str,
    published: str,
    region: str,
    category: str,
    payload: dict[str, Any],
    trust: str | None = None,
) -> bool:
    title = normalize_title(title)
    category = classify_category(title, category)
    confidence = source_confidence(source, trust)
    existing = conn.execute(
        "SELECT id FROM raw_documents WHERE source_url = ? OR (source = ? AND title_cn = ?)",
        (url, source, title),
    ).fetchone()
    if existing:
        return False

    sentiment = sentiment_score(title)
    severity = severity_score(title, category)
    doc_id = new_id("doc")
    conn.execute(
        """
        INSERT INTO raw_documents (
            id, fetched_at, source, source_url, title_cn, title_en, published_at,
            region, category, severity, sentiment, confidence, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            now_iso(),
            source,
            url,
            title,
            title,
            published,
            region,
            category,
            severity,
            sentiment,
            confidence,
            json_dumps(payload),
        ),
    )
    conn.execute(
        """
        INSERT INTO events (
            id, created_at, title_cn, title_en, source_type, region, category,
            severity, sentiment, confidence, link, is_fact, notes_cn, notes_en
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("event"),
            now_iso(),
            title,
            title,
            source,
            region,
            category,
            severity,
            sentiment,
            confidence,
            url,
            1,
            "动态公开数据管道抓取并入库。",
            "Fetched by the dynamic public data pipeline.",
        ),
    )
    return True


def latest_market_value(conn, symbol: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM market_data_history
        WHERE symbol = ?
        ORDER BY fetched_at DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    return dict(row) if row else None


def latest_by_asset_or_symbol(conn, asset_id: str | None, symbol: str) -> dict[str, Any] | None:
    if asset_id:
        row = conn.execute(
            """
            SELECT * FROM market_data_history
            WHERE asset_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
        if row:
            return dict(row)
    return latest_market_value(conn, symbol)


def rebuild_market_snapshot(conn) -> str:
    csi300 = latest_market_value(conn, "000300.SH")
    sp500 = latest_market_value(conn, "SPX")
    hsi = latest_by_asset_or_symbol(conn, "asset_159920", "159920.SZ")
    usdcnh = latest_market_value(conn, "USD/CNH")
    gold = latest_by_asset_or_symbol(conn, "asset_518880", "XAUUSD")
    oil = latest_by_asset_or_symbol(conn, "asset_162411", "CL.F")

    recent_docs = rows_to_dicts(
        conn.execute(
            """
            SELECT * FROM raw_documents
            ORDER BY fetched_at DESC
            LIMIT 30
            """
        ).fetchall()
    )
    policy_score = sum(doc["sentiment"] for doc in recent_docs if doc["category"] in {"policy", "macro", "market"})
    geo_count = sum(1 for doc in recent_docs if doc["category"] == "geopolitics" and doc["severity"] >= 3)
    liquidity_signal = "neutral"
    policy_signal = "positive" if policy_score > 1 else "negative" if policy_score < -1 else "neutral"
    geopolitics_signal = "elevated" if geo_count >= 2 else "neutral"

    snapshot_id = new_id("snapshot")
    headline_cn = build_snapshot_headline(policy_signal, geopolitics_signal, recent_docs, "cn")
    headline_en = build_snapshot_headline(policy_signal, geopolitics_signal, recent_docs, "en")
    conn.execute(
        """
        INSERT INTO market_snapshots (
            id, as_of, headline_cn, headline_en, csi300_change, sp500_change,
            hsi_change, usdcnh_change, gold_change, oil_change, policy_signal,
            geopolitics_signal, liquidity_signal, source_quality, notes_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            date.today().isoformat(),
            headline_cn,
            headline_en,
            float((csi300 or {}).get("day_change_pct", 0.0)),
            float((sp500 or {}).get("day_change_pct", 0.0)),
            float((hsi or {}).get("day_change_pct", 0.0)),
            float((usdcnh or {}).get("day_change_pct", 0.0)),
            float((gold or {}).get("day_change_pct", 0.0)),
            float((oil or {}).get("day_change_pct", 0.0)),
            policy_signal,
            geopolitics_signal,
            liquidity_signal,
            "public_dynamic" if recent_docs or csi300 or sp500 else "seed_demo",
            json_dumps(
                {
                    "docs": len(recent_docs),
                    "quotes": {
                        "csi300": bool(csi300),
                        "sp500": bool(sp500),
                        "hsi": bool(hsi),
                        "usdcnh": bool(usdcnh),
                        "gold": bool(gold),
                        "oil": bool(oil),
                    },
                    "generated_at": now_iso(),
                }
            ),
        ),
    )
    return snapshot_id


def build_snapshot_headline(policy_signal: str, geo_signal: str, docs: list[dict[str, Any]], lang: str) -> str:
    lead = docs[0]["title_cn"] if docs else ""
    if lang == "cn":
        policy = "政策/宏观线索偏积极" if policy_signal == "positive" else "政策/宏观线索偏谨慎" if policy_signal == "negative" else "政策/宏观线索中性"
        geo = "地缘风险偏高" if geo_signal == "elevated" else "地缘风险中性"
        return f"{policy}，{geo}；最新公共信息：{lead or '暂无新增重大公共信息'}。"
    policy_en = "policy/macro cues are constructive" if policy_signal == "positive" else "policy/macro cues are cautious" if policy_signal == "negative" else "policy/macro cues are neutral"
    geo_en = "geopolitical risk is elevated" if geo_signal == "elevated" else "geopolitical risk is neutral"
    return f"{policy_en}; {geo_en}; latest public signal: {lead or 'no major new public item'}."


def list_source_runs(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                """
                SELECT * FROM source_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )


def list_raw_documents(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                """
                SELECT id, fetched_at, source, source_url, title_cn, title_en, published_at,
                       region, category, severity, sentiment, confidence
                FROM raw_documents
                ORDER BY fetched_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )
