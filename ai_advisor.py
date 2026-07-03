from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import date
from typing import Any

from .config import DATA_DIR, RISK_POLICY
from .db import connect, json_dumps, new_id, now_iso, row_to_dict, rows_to_dicts
from .engine import latest_report, portfolio_state, stock_rows
from .universe import universe_rows, universe_summary


SECRETS_PATH = DATA_DIR / "secrets.json"


def load_ai_config() -> dict[str, str]:
    file_config: dict[str, str] = {}
    if SECRETS_PATH.exists():
        file_config = json.loads(SECRETS_PATH.read_text(encoding="utf-8-sig"))
    return {
        "api_key": os.getenv("SIMVEST_LLM_API_KEY") or file_config.get("api_key", ""),
        "base_url": os.getenv("SIMVEST_LLM_BASE_URL")
        or file_config.get("base_url", "https://api.deepseek.com/chat/completions"),
        "model": os.getenv("SIMVEST_LLM_MODEL") or file_config.get("model", "deepseek-chat"),
        "provider": os.getenv("SIMVEST_LLM_PROVIDER") or file_config.get("provider", "openai-compatible"),
    }


def build_advice_context() -> dict[str, Any]:
    with connect() as conn:
        portfolio = portfolio_state(conn)
        assets = rows_to_dicts(
            conn.execute(
                """
                SELECT symbol, name_cn, name_en, asset_class, product_type, bucket, market,
                       region, currency, price, day_change_pct, ytd_return_pct,
                       volatility_20d, risk_bucket, tradable
                FROM assets
                ORDER BY asset_class, market, symbol
                """
            ).fetchall()
        )
        events = rows_to_dicts(
            conn.execute(
                """
                SELECT created_at, title_cn, title_en, source_type, region, category,
                       severity, sentiment, confidence, link
                FROM events
                ORDER BY created_at DESC
                LIMIT 60
                """
            ).fetchall()
        )
        snapshots = rows_to_dicts(
            conn.execute(
                """
                SELECT as_of, headline_cn, headline_en, csi300_change, sp500_change,
                       hsi_change, usdcnh_change, gold_change, oil_change,
                       policy_signal, geopolitics_signal, liquidity_signal, source_quality
                FROM market_snapshots
                ORDER BY rowid DESC
                LIMIT 3
                """
            ).fetchall()
        )
    report = latest_report()
    stocks = stock_rows()
    universe_context = {
        "summary": universe_summary(),
        "top_turnover": universe_rows({"limit": ["30"], "sort": ["turnover"], "direction": ["desc"]})["rows"],
        "top_gainers": universe_rows({"limit": ["20"], "sort": ["change"], "direction": ["desc"]})["rows"],
        "top_losers": universe_rows({"limit": ["20"], "sort": ["change"], "direction": ["asc"]})["rows"],
    }
    return {
        "as_of": date.today().isoformat(),
        "portfolio": portfolio,
        "assets": assets,
        "stocks": stocks,
        "market_universe": universe_context,
        "events": events,
        "market_snapshots": snapshots,
        "latest_report": compact_report(report),
        "risk_policy": RISK_POLICY,
        "hard_constraints": [
            "仅模拟投资，不发送真实券商订单。",
            "不允许做空。",
            "不允许使用杠杆。",
            "优先选择普通人低门槛、公开市场可获得的产品。",
            "最大回撤偏好为20%。",
            "任何交易建议必须等待人工确认后才可记录模拟交易。",
        ],
    }


def compact_report(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not report:
        return None
    return {
        "id": report.get("id"),
        "as_of": report.get("as_of"),
        "thesis_cn": report.get("thesis_cn"),
        "chain_cn": report.get("chain_cn"),
        "risk_level": report.get("risk_level"),
        "regime": report.get("regime"),
        "confidence": report.get("confidence"),
        "decisions": [
            {
                "symbol": decision.get("symbol"),
                "action": decision.get("action"),
                "target_weight": decision.get("target_weight"),
                "amount_cny": decision.get("amount_cny"),
                "confidence": decision.get("confidence"),
                "status": decision.get("status"),
            }
            for decision in report.get("decisions", [])[:20]
        ],
    }


def generate_ai_advice() -> dict[str, Any]:
    config = load_ai_config()
    context = build_advice_context()
    advice_id = new_id("ai")
    created_at = now_iso()

    if not config["api_key"]:
        return save_ai_advice(
            advice_id,
            created_at,
            config,
            "missing_key",
            "",
            context,
            {},
            "Missing SIMVEST_LLM_API_KEY or data/secrets.json api_key",
        )

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个严格风控的模拟投资投研助手。你只提供模拟投资建议，不能承诺收益，"
                "不能暗示真实下单已经发生。你必须遵守：不做空、不使用杠杆、普通人低门槛公开市场产品优先、"
                "人工确认后才可记录模拟交易、最大回撤偏好20%。"
                "输出中文为主，关键术语可附英文。结构必须包含：市场主线、持仓盈亏解读、板块判断、"
                "具体模拟建议、触发条件、止损止盈、持有周期、风险条件、今日不做什么。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请基于以下已抓取数据生成当日模拟投资建议。建议要具体到标的、方向、仓位调整、"
                "模拟金额、参考价格、止损、止盈、持有周期和置信度。请明确说明这只是模拟建议，"
                "所有动作必须等待人工确认。\n\n"
                + json.dumps(context, ensure_ascii=False)
            ),
        },
    ]
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2400,
    }
    req = urllib.request.Request(
        config["base_url"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
        advice_text = extract_advice_text(raw)
        return save_ai_advice(advice_id, created_at, config, "ok", advice_text, context, raw, "")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return save_ai_advice(
            advice_id,
            created_at,
            config,
            "error",
            "",
            context,
            {},
            f"HTTP {exc.code}: {error_body[:1000]}",
        )
    except Exception as exc:
        return save_ai_advice(advice_id, created_at, config, "error", "", context, {}, str(exc))


def extract_advice_text(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        if message.get("content"):
            return str(message["content"])
    if raw.get("output_text"):
        return str(raw["output_text"])
    return json.dumps(raw, ensure_ascii=False, indent=2)[:4000]


def save_ai_advice(
    advice_id: str,
    created_at: str,
    config: dict[str, str],
    status: str,
    advice_text: str,
    context: dict[str, Any],
    raw: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ai_advice (
                id, created_at, as_of, provider, model, status, advice_text,
                context_json, raw_json, error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                advice_id,
                created_at,
                context["as_of"],
                config.get("provider", "openai-compatible"),
                config.get("model", ""),
                status,
                advice_text,
                json_dumps(context),
                json_dumps(raw),
                error,
            ),
        )
    return {
        "id": advice_id,
        "created_at": created_at,
        "as_of": context["as_of"],
        "provider": config.get("provider", "openai-compatible"),
        "model": config.get("model", ""),
        "status": status,
        "advice_text": advice_text,
        "error": error,
    }


def latest_ai_advice() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, created_at, as_of, provider, model, status, advice_text, error
            FROM ai_advice
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row_to_dict(row)
