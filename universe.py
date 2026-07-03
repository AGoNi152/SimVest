from __future__ import annotations

import contextlib
import io
import json
import math
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Any

from .db import connect, json_dumps, new_id, now_iso, row_to_dict, rows_to_dicts


EASTMONEY_ENDPOINT = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_FIELDS = ",".join(
    [
        "f12",  # code
        "f14",  # name
        "f2",  # latest price
        "f3",  # pct change
        "f4",  # change value
        "f5",  # volume
        "f6",  # turnover
        "f7",  # amplitude
        "f8",  # turnover rate
        "f9",  # pe
        "f15",  # high
        "f16",  # low
        "f17",  # open
        "f18",  # prev close
        "f20",  # market cap
        "f21",  # float market cap
        "f23",  # pb
        "f100",  # sector
        "f102",  # board / region board
    ]
)


UNIVERSE_SOURCES = [
    {
        "id": "a_share_equity",
        "name": "A股股票",
        "market": "CN",
        "region": "中国大陆",
        "asset_class": "equity",
        "product_type": "A Share",
        "currency": "CNY",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
    },
    {
        "id": "hk_equity",
        "name": "港股股票",
        "market": "HK",
        "region": "香港",
        "asset_class": "equity",
        "product_type": "HK Stock",
        "currency": "HKD",
        "fs": "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2",
    },
    {
        "id": "cn_etf_fund",
        "name": "中国场内基金ETF",
        "market": "CN",
        "region": "中国大陆",
        "asset_class": "fund",
        "product_type": "ETF / LOF",
        "currency": "CNY",
        "fs": "b:MK0021,b:MK0022,b:MK0023,b:MK0024",
    },
]

ORDER_COLUMNS = {
    "symbol": "symbol",
    "name": "name_cn",
    "price": "price",
    "change": "day_change_pct",
    "turnover": "turnover",
    "market_cap": "market_cap",
    "sector": "sector",
    "updated_at": "updated_at",
}


def safe_float(value: Any) -> float | None:
    if value in (None, "", "-", "N/A", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def eastmoney_json(params: dict[str, Any], timeout: int = 15) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, safe=",:+")
    url = f"{EASTMONEY_ENDPOINT}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return eastmoney_json_via_powershell(url, timeout)


def eastmoney_json_via_powershell(url: str, timeout: int) -> dict[str, Any]:
    safe_url = url.replace("'", "''")
    command = (
        "$ProgressPreference='SilentlyContinue'; "
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        f"(Invoke-WebRequest -Uri '{safe_url}' -UseBasicParsing).Content"
    )
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            command,
        ],
        capture_output=True,
        timeout=timeout + 10,
        check=True,
    )
    text = completed.stdout.decode("utf-8-sig", errors="replace")
    return json.loads(text)


def cn_symbol(code: str, product_type: str) -> str:
    lowered = code.lower()
    if lowered.startswith("sh"):
        return f"{code[-6:]}.SH"
    if lowered.startswith("sz"):
        return f"{code[-6:]}.SZ"
    if lowered.startswith("bj"):
        return f"{code[-6:]}.BJ"
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "1", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    suffix = "ETF" if "ETF" in product_type.upper() else "CN"
    return f"{code}.{suffix}"


def hk_symbol(code: str) -> str:
    normalized = code.strip()
    if len(normalized) == 5 and normalized.startswith("0"):
        normalized = normalized[1:]
    return f"{normalized.zfill(4)}.HK"


def board_from_cn_code(code: str) -> str:
    lowered = code.lower()
    bare = lowered[-6:]
    if lowered.startswith("bj") or bare.startswith(("8", "4", "9")):
        return "北交所"
    if bare.startswith("688"):
        return "科创板"
    if bare.startswith(("300", "301")):
        return "创业板"
    if bare.startswith("6"):
        return "上交所主板"
    if bare.startswith(("0", "2")):
        return "深交所主板"
    if bare.startswith(("5", "1")):
        return "场内基金"
    return "未分类"


def normalize_record(raw: dict[str, Any], source: dict[str, Any], source_url: str) -> dict[str, Any]:
    code = str(raw.get("f12") or "").strip()
    if source["market"] == "HK":
        symbol = hk_symbol(code)
    else:
        symbol = cn_symbol(code, source["product_type"])
    price = safe_float(raw.get("f2"))
    prev_close = safe_float(raw.get("f18"))
    return {
        "symbol": symbol,
        "code": code,
        "name_cn": str(raw.get("f14") or "").strip() or symbol,
        "name_en": "",
        "market": source["market"],
        "region": source["region"],
        "asset_class": source["asset_class"],
        "product_type": source["product_type"],
        "sector": str(raw.get("f100") or "").strip() or "未分类",
        "board": str(raw.get("f102") or "").strip() or "未分类",
        "currency": source["currency"],
        "price": price,
        "prev_close": prev_close,
        "day_change_pct": safe_float(raw.get("f3")),
        "change_value": safe_float(raw.get("f4")),
        "volume": safe_float(raw.get("f5")),
        "turnover": safe_float(raw.get("f6")),
        "turnover_rate": safe_float(raw.get("f8")),
        "amplitude": safe_float(raw.get("f7")),
        "high": safe_float(raw.get("f15")),
        "low": safe_float(raw.get("f16")),
        "open_price": safe_float(raw.get("f17")),
        "market_cap": safe_float(raw.get("f20")),
        "float_market_cap": safe_float(raw.get("f21")),
        "pe_ttm": safe_float(raw.get("f9")),
        "pb": safe_float(raw.get("f23")),
        "source": "Eastmoney",
        "source_url": source_url,
        "tradable": 1 if price is not None else 0,
        "updated_at": now_iso(),
        "payload_json": json_dumps(raw),
    }


def fetch_source(source: dict[str, Any], page_size: int = 500, timeout: int = 15) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    total = None
    try:
        while True:
            params = {
                "pn": page,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": source["fs"],
                "fields": EASTMONEY_FIELDS,
            }
            source_url = f"{EASTMONEY_ENDPOINT}?{urllib.parse.urlencode(params, safe=',:+')}"
            payload = eastmoney_json(params, timeout=timeout)
            data = payload.get("data") or {}
            total = int(data.get("total") or 0)
            diff = data.get("diff") or []
            for raw in diff:
                record = normalize_record(raw, source, source_url)
                if record["code"]:
                    records.append(record)
            if not diff or len(records) >= total:
                break
            page += 1
            time.sleep(0.12)
        return records
    except Exception:
        return fetch_source_akshare(source)


def fetch_source_akshare(source: dict[str, Any]) -> list[dict[str, Any]]:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        import akshare as ak  # type: ignore

        if source["id"] == "a_share_equity":
            df = ak.stock_zh_a_spot()
        elif source["id"] == "hk_equity":
            df = ak.stock_hk_spot()
        elif source["id"] == "cn_etf_fund":
            df = ak.fund_etf_category_sina(symbol="ETF基金")
        else:
            return []
    rows = df.to_dict(orient="records")
    if source["id"] == "a_share_equity":
        return [normalize_akshare_a(row, source) for row in rows]
    if source["id"] == "hk_equity":
        return [normalize_akshare_hk(row, source) for row in rows]
    if source["id"] == "cn_etf_fund":
        return [normalize_akshare_etf(row, source) for row in rows]
    return []


def normalize_akshare_a(raw: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    code = str(raw.get("代码") or "").strip()
    symbol = cn_symbol(code, source["product_type"])
    return {
        "symbol": symbol,
        "code": code[-6:],
        "name_cn": str(raw.get("名称") or "").strip() or symbol,
        "name_en": "",
        "market": source["market"],
        "region": source["region"],
        "asset_class": source["asset_class"],
        "product_type": source["product_type"],
        "sector": "未分类",
        "board": board_from_cn_code(code),
        "currency": source["currency"],
        "price": safe_float(raw.get("最新价")),
        "prev_close": safe_float(raw.get("昨收")),
        "day_change_pct": safe_float(raw.get("涨跌幅")),
        "change_value": safe_float(raw.get("涨跌额")),
        "volume": safe_float(raw.get("成交量")),
        "turnover": safe_float(raw.get("成交额")),
        "turnover_rate": None,
        "amplitude": None,
        "high": safe_float(raw.get("最高")),
        "low": safe_float(raw.get("最低")),
        "open_price": safe_float(raw.get("今开")),
        "market_cap": None,
        "float_market_cap": None,
        "pe_ttm": None,
        "pb": None,
        "source": "AkShare/Sina",
        "source_url": "akshare.stock_zh_a_spot",
        "tradable": 1 if safe_float(raw.get("最新价")) is not None else 0,
        "updated_at": now_iso(),
        "payload_json": json_dumps(raw),
    }


def normalize_akshare_hk(raw: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    code = str(raw.get("代码") or "").strip()
    symbol = hk_symbol(code)
    return {
        "symbol": symbol,
        "code": code.zfill(5),
        "name_cn": str(raw.get("中文名称") or "").strip() or symbol,
        "name_en": str(raw.get("英文名称") or "").strip(),
        "market": source["market"],
        "region": source["region"],
        "asset_class": source["asset_class"],
        "product_type": source["product_type"],
        "sector": "未分类",
        "board": "港股",
        "currency": source["currency"],
        "price": safe_float(raw.get("最新价")),
        "prev_close": safe_float(raw.get("昨收")),
        "day_change_pct": safe_float(raw.get("涨跌幅")),
        "change_value": safe_float(raw.get("涨跌额")),
        "volume": safe_float(raw.get("成交量")),
        "turnover": safe_float(raw.get("成交额")),
        "turnover_rate": None,
        "amplitude": None,
        "high": safe_float(raw.get("最高")),
        "low": safe_float(raw.get("最低")),
        "open_price": safe_float(raw.get("今开")),
        "market_cap": None,
        "float_market_cap": None,
        "pe_ttm": None,
        "pb": None,
        "source": "AkShare/HK",
        "source_url": "akshare.stock_hk_spot",
        "tradable": 1 if safe_float(raw.get("最新价")) is not None else 0,
        "updated_at": now_iso(),
        "payload_json": json_dumps(raw),
    }


def normalize_akshare_etf(raw: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    code = str(raw.get("代码") or "").strip()
    symbol = cn_symbol(code, source["product_type"])
    return {
        "symbol": symbol,
        "code": code[-6:],
        "name_cn": str(raw.get("名称") or "").strip() or symbol,
        "name_en": "",
        "market": source["market"],
        "region": source["region"],
        "asset_class": source["asset_class"],
        "product_type": source["product_type"],
        "sector": "ETF基金",
        "board": board_from_cn_code(code),
        "currency": source["currency"],
        "price": safe_float(raw.get("最新价")),
        "prev_close": safe_float(raw.get("昨收")),
        "day_change_pct": safe_float(raw.get("涨跌幅")),
        "change_value": safe_float(raw.get("涨跌额")),
        "volume": safe_float(raw.get("成交量")),
        "turnover": safe_float(raw.get("成交额")),
        "turnover_rate": None,
        "amplitude": None,
        "high": safe_float(raw.get("最高")),
        "low": safe_float(raw.get("最低")),
        "open_price": safe_float(raw.get("今开")),
        "market_cap": None,
        "float_market_cap": None,
        "pe_ttm": None,
        "pb": None,
        "source": "AkShare/Sina ETF",
        "source_url": "akshare.fund_etf_category_sina",
        "tradable": 1 if safe_float(raw.get("最新价")) is not None else 0,
        "updated_at": now_iso(),
        "payload_json": json_dumps(raw),
    }


def upsert_universe_records(conn, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    conn.executemany(
        """
        INSERT INTO market_universe (
            symbol, code, name_cn, name_en, market, region, asset_class, product_type,
            sector, board, currency, price, prev_close, day_change_pct, change_value,
            volume, turnover, turnover_rate, amplitude, high, low, open_price,
            market_cap, float_market_cap, pe_ttm, pb, source, source_url, tradable,
            updated_at, payload_json
        )
        VALUES (
            :symbol, :code, :name_cn, :name_en, :market, :region, :asset_class,
            :product_type, :sector, :board, :currency, :price, :prev_close,
            :day_change_pct, :change_value, :volume, :turnover, :turnover_rate,
            :amplitude, :high, :low, :open_price, :market_cap, :float_market_cap,
            :pe_ttm, :pb, :source, :source_url, :tradable, :updated_at, :payload_json
        )
        ON CONFLICT(symbol) DO UPDATE SET
            code = excluded.code,
            name_cn = excluded.name_cn,
            name_en = excluded.name_en,
            market = excluded.market,
            region = excluded.region,
            asset_class = excluded.asset_class,
            product_type = excluded.product_type,
            sector = excluded.sector,
            board = excluded.board,
            currency = excluded.currency,
            price = excluded.price,
            prev_close = excluded.prev_close,
            day_change_pct = excluded.day_change_pct,
            change_value = excluded.change_value,
            volume = excluded.volume,
            turnover = excluded.turnover,
            turnover_rate = excluded.turnover_rate,
            amplitude = excluded.amplitude,
            high = excluded.high,
            low = excluded.low,
            open_price = excluded.open_price,
            market_cap = excluded.market_cap,
            float_market_cap = excluded.float_market_cap,
            pe_ttm = excluded.pe_ttm,
            pb = excluded.pb,
            source = excluded.source,
            source_url = excluded.source_url,
            tradable = excluded.tradable,
            updated_at = excluded.updated_at,
            payload_json = excluded.payload_json
        """,
        records,
    )


def insert_history_records(conn, records: list[dict[str, Any]]) -> None:
    fetched_at = now_iso()
    conn.executemany(
        """
        INSERT INTO market_universe_history (
            id, fetched_at, symbol, market, asset_class, product_type, price,
            prev_close, day_change_pct, turnover, source, payload_json
        )
        VALUES (
            :id, :fetched_at, :symbol, :market, :asset_class, :product_type, :price,
            :prev_close, :day_change_pct, :turnover, :source, :payload_json
        )
        """,
        [
            {
                "id": new_id("unih"),
                "fetched_at": fetched_at,
                "symbol": record["symbol"],
                "market": record["market"],
                "asset_class": record["asset_class"],
                "product_type": record["product_type"],
                "price": record["price"],
                "prev_close": record["prev_close"],
                "day_change_pct": record["day_change_pct"],
                "turnover": record["turnover"],
                "source": record["source"],
                "payload_json": record["payload_json"],
            }
            for record in records
            if record.get("price") is not None
        ],
    )


def sync_market_universe(timeout: int = 15) -> dict[str, Any]:
    started_at = now_iso()
    run_id = new_id("run")
    results = []
    total_records = 0
    status = "ok"
    error_messages = []
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO source_runs (id, source, started_at, finished_at, status, records, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, "market_universe", started_at, None, "running", 0, ""),
        )
        try:
            for source in UNIVERSE_SOURCES:
                try:
                    records = fetch_source(source, timeout=timeout)
                    conn.execute("BEGIN")
                    conn.execute(
                        """
                        DELETE FROM market_universe
                        WHERE market = ? AND asset_class = ? AND product_type = ?
                        """,
                        (source["market"], source["asset_class"], source["product_type"]),
                    )
                    upsert_universe_records(conn, records)
                    insert_history_records(conn, records)
                    conn.execute("COMMIT")
                    total_records += len(records)
                    results.append({"source": source["id"], "records": len(records), "status": "ok", "error": ""})
                except Exception as exc:  # pragma: no cover - external data source boundary
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass
                    status = "partial_error"
                    message = f"{source['id']}: {exc}"
                    error_messages.append(message)
                    results.append({"source": source["id"], "records": 0, "status": "error", "error": str(exc)})
            conn.execute(
                """
                UPDATE source_runs
                SET finished_at = ?, status = ?, records = ?, error = ?
                WHERE id = ?
                """,
                (now_iso(), status, total_records, "; ".join(error_messages), run_id),
            )
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return {"status": status, "records": total_records, "results": results}


def universe_summary() -> dict[str, Any]:
    with connect() as conn:
        total = int(conn.execute("SELECT COUNT(*) FROM market_universe").fetchone()[0])
        by_market = rows_to_dicts(
            conn.execute(
                """
                SELECT market, COUNT(*) AS count
                FROM market_universe
                GROUP BY market
                ORDER BY count DESC
                """
            ).fetchall()
        )
        by_asset_class = rows_to_dicts(
            conn.execute(
                """
                SELECT asset_class, product_type, COUNT(*) AS count
                FROM market_universe
                GROUP BY asset_class, product_type
                ORDER BY count DESC
                """
            ).fetchall()
        )
        top_sectors = rows_to_dicts(
            conn.execute(
                """
                SELECT sector, COUNT(*) AS count
                FROM market_universe
                WHERE sector <> ''
                GROUP BY sector
                ORDER BY count DESC
                LIMIT 30
                """
            ).fetchall()
        )
        latest = row_to_dict(
            conn.execute(
                """
                SELECT MAX(updated_at) AS updated_at, MAX(source) AS source
                FROM market_universe
                """
            ).fetchone()
        )
    return {
        "total": total,
        "by_market": by_market,
        "by_asset_class": by_asset_class,
        "top_sectors": top_sectors,
        "latest": latest,
    }


def universe_rows(query: dict[str, list[str]]) -> dict[str, Any]:
    limit = min(500, max(20, int((query.get("limit") or ["100"])[0])))
    offset = max(0, int((query.get("offset") or ["0"])[0]))
    sort_key = (query.get("sort") or ["turnover"])[0]
    direction = (query.get("direction") or ["desc"])[0].lower()
    order_col = ORDER_COLUMNS.get(sort_key, "turnover")
    order_direction = "ASC" if direction == "asc" else "DESC"
    filters = []
    params: list[Any] = []
    for key, column in [("market", "market"), ("asset_class", "asset_class"), ("product_type", "product_type"), ("sector", "sector")]:
        value = (query.get(key) or [""])[0].strip()
        if value:
            filters.append(f"{column} = ?")
            params.append(value)
    search = (query.get("search") or [""])[0].strip()
    if search:
        like = f"%{search}%"
        filters.append("(symbol LIKE ? OR code LIKE ? OR name_cn LIKE ? OR sector LIKE ? OR board LIKE ?)")
        params.extend([like, like, like, like, like])
    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    with connect() as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM market_universe {where}", params).fetchone()[0])
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT *
                FROM market_universe
                {where}
                ORDER BY {order_col} {order_direction}, symbol ASC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        )
    return {"rows": rows, "total": total, "limit": limit, "offset": offset}


def universe_detail(symbol: str) -> dict[str, Any] | None:
    normalized = symbol.strip().upper()
    with connect() as conn:
        item = row_to_dict(
            conn.execute("SELECT * FROM market_universe WHERE UPPER(symbol) = ? LIMIT 1", (normalized,)).fetchone()
        )
        if not item:
            return None
        history = rows_to_dicts(
            conn.execute(
                """
                SELECT fetched_at, symbol, market, asset_class, product_type, price,
                       prev_close, day_change_pct, turnover, source
                FROM market_universe_history
                WHERE UPPER(symbol) = ?
                ORDER BY fetched_at DESC
                LIMIT 90
                """,
                (normalized,),
            ).fetchall()
        )
        related_core_asset = row_to_dict(
            conn.execute("SELECT * FROM assets WHERE UPPER(symbol) = ? LIMIT 1", (normalized,)).fetchone()
        )
    chronological = list(reversed(history))
    risk_flags = []
    if abs(safe_float(item.get("day_change_pct")) or 0) >= 5:
        risk_flags.append("单日波动较大")
    if safe_float(item.get("turnover")) and safe_float(item.get("turnover")) < 5_000_000:
        risk_flags.append("成交额偏低")
    if item.get("pe_ttm") is not None and safe_float(item.get("pe_ttm")) is not None and (safe_float(item.get("pe_ttm")) or 0) < 0:
        risk_flags.append("盈利为负或市盈率不可比")
    if item.get("asset_class") == "equity" and not related_core_asset:
        risk_flags.append("尚未进入核心模拟投资池")
    return {
        "item": item,
        "history": chronological,
        "core_asset": related_core_asset,
        "risk_flags": risk_flags,
        "view": "核心池标的" if related_core_asset else "全市场观察",
    }
