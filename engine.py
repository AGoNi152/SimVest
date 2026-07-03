from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any

from .config import (
    FEE_POLICY,
    INITIAL_CAPITAL,
    PROFILE_ALLOCATIONS,
    RISK_POLICY,
    STOP_RULES,
)
from .db import connect, json_dumps, new_id, now_iso, row_to_dict, rows_to_dicts


FX_TO_CNY = {
    "CNY": 1.0,
    "HKD": 0.92,
    "USD": 7.25,
}


def currency_to_cny(currency: str) -> float:
    return FX_TO_CNY.get(currency.upper(), 1.0)


def round_confidence(value: float) -> int:
    step = int(RISK_POLICY["decision_confidence_step_pct"])
    return max(5, min(95, int(round(value / step) * step)))


def fetch_assets(conn) -> list[dict[str, Any]]:
    return rows_to_dicts(conn.execute("SELECT * FROM assets ORDER BY bucket, symbol").fetchall())


def fetch_latest_snapshot(conn) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM market_snapshots ORDER BY as_of DESC, rowid DESC LIMIT 1"
    ).fetchone()
    return row_to_dict(row) or {}


def fetch_recent_events(conn, limit: int = 12) -> list[dict[str, Any]]:
    return rows_to_dicts(
        conn.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    )


def fetch_positions(conn) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            p.*,
            a.symbol,
            a.name_cn,
            a.name_en,
            a.asset_class,
            a.product_type,
            a.bucket,
            a.market,
            a.region,
            a.currency,
            a.price
        FROM positions p
        JOIN assets a ON a.id = p.asset_id
        ORDER BY p.market_value DESC
        """
    ).fetchall()
    return rows_to_dicts(rows)


def refresh_positions_market_values(conn) -> None:
    rows = conn.execute(
        """
        SELECT
            p.id,
            p.quantity,
            p.avg_cost,
            a.price,
            a.currency
        FROM positions p
        JOIN assets a ON a.id = p.asset_id
        """
    ).fetchall()
    cash = latest_cash(conn)
    position_values: list[tuple[str, float, float, float, float]] = []
    positions_value = 0.0
    for row in rows:
        fx = currency_to_cny(row["currency"])
        market_price = float(row["price"])
        market_value = float(row["quantity"]) * market_price * fx
        cost_value = float(row["quantity"]) * float(row["avg_cost"]) * fx
        positions_value += market_value
        position_values.append((row["id"], market_price, market_value, cost_value, fx))

    total = cash + positions_value
    for position_id, market_price, market_value, _cost_value, _fx in position_values:
        weight = market_value / total if total else 0.0
        conn.execute(
            """
            UPDATE positions
            SET market_price = ?, market_value = ?, weight = ?, updated_at = ?
            WHERE id = ?
            """,
            (market_price, market_value, weight, now_iso(), position_id),
        )


def portfolio_state(conn) -> dict[str, Any]:
    refresh_positions_market_values(conn)
    cash = latest_cash(conn)
    positions = fetch_positions(conn)
    positions_value = sum(float(position["market_value"]) for position in positions)
    total_value = cash + positions_value
    exposures: dict[str, float] = {}
    total_cost = 0.0
    total_pnl = 0.0
    for position in positions:
        fx = currency_to_cny(str(position["currency"]))
        cost_value = float(position["quantity"]) * float(position["avg_cost"]) * fx
        market_value = float(position["market_value"])
        pnl = market_value - cost_value
        pnl_pct = pnl / cost_value * 100 if cost_value else 0.0
        position["cost_value"] = round(cost_value, 2)
        position["unrealized_pnl"] = round(pnl, 2)
        position["unrealized_pnl_pct"] = round(pnl_pct, 2)
        position["market_price"] = float(position["price"])
        weight = float(position["market_value"]) / total_value if total_value else 0.0
        position["weight"] = weight
        exposures[position["bucket"]] = exposures.get(position["bucket"], 0.0) + weight
        total_cost += cost_value
        total_pnl += pnl
    total_return = (total_value / INITIAL_CAPITAL - 1) * 100 if INITIAL_CAPITAL else 0.0
    invested_return = total_pnl / total_cost * 100 if total_cost else 0.0
    return {
        "cash": cash,
        "positions": positions,
        "positions_value": positions_value,
        "total_value": total_value,
        "cash_weight": cash / total_value if total_value else 1.0,
        "exposures": exposures,
        "initial_capital": INITIAL_CAPITAL,
        "total_pnl": round(total_value - INITIAL_CAPITAL, 2),
        "total_pnl_pct": round(total_return, 2),
        "invested_cost": round(total_cost, 2),
        "unrealized_pnl": round(total_pnl, 2),
        "unrealized_pnl_pct": round(invested_return, 2),
    }


def latest_cash(conn) -> float:
    row = conn.execute(
        "SELECT balance_after FROM cash_ledger ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return float(row["balance_after"]) if row else INITIAL_CAPITAL


def compute_risk_score(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> tuple[int, str]:
    score = 36.0
    csi300 = float(snapshot.get("csi300_change", 0.0))
    sp500 = float(snapshot.get("sp500_change", 0.0))
    hsi = float(snapshot.get("hsi_change", 0.0))
    usdcnh = float(snapshot.get("usdcnh_change", 0.0))
    gold = float(snapshot.get("gold_change", 0.0))
    oil = float(snapshot.get("oil_change", 0.0))

    for change, weight in [(csi300, 6), (sp500, 5), (hsi, 5)]:
        if change < -1.0:
            score += abs(change) * weight
        elif change > 0.8:
            score -= min(6, change * 2)

    if usdcnh > 0.35:
        score += 6
    if gold > 1.0:
        score += 3
    if oil > 2.0:
        score += 4

    policy_signal = snapshot.get("policy_signal", "neutral")
    if policy_signal == "positive":
        score -= 8
    elif policy_signal == "negative":
        score += 8

    if snapshot.get("liquidity_signal") == "tight":
        score += 7
    elif snapshot.get("liquidity_signal") == "loose":
        score -= 5

    for event in events:
        severity = int(event.get("severity", 0))
        sentiment = int(event.get("sentiment", 0))
        category = str(event.get("category", ""))
        if sentiment < 0:
            score += severity * (2.5 if category == "geopolitics" else 1.8)
        elif sentiment > 0:
            score -= severity * 1.5

    score = int(max(0, min(100, round(score))))
    if score >= 75:
        level = "stressed"
    elif score >= 55:
        level = "elevated"
    elif score >= 35:
        level = "balanced"
    else:
        level = "constructive"
    return score, level


def choose_profile(risk_score: int) -> str:
    if risk_score >= 65:
        return "conservative"
    if risk_score <= 32:
        return "growth"
    return "standard"


def target_asset_weights(
    profile_name: str,
    assets: list[dict[str, Any]],
) -> dict[str, float]:
    allocation = PROFILE_ALLOCATIONS[profile_name]
    by_id = {asset["id"]: asset for asset in assets}
    targets = {
        "asset_510300": allocation["china_equity"] * 0.70,
        "asset_510880": allocation["china_equity"] * 0.30,
        "asset_159920": allocation["hk_equity"] * 0.72,
        "asset_0700hk": allocation["hk_equity"] * 0.28,
        "asset_513500": allocation["global_equity"],
        "asset_511010": allocation["bond"],
        "asset_511880": allocation["money"],
        "asset_518880": allocation["gold"],
        "asset_162411": allocation["oil"],
    }

    capped: dict[str, float] = {}
    spare = 0.0
    for asset_id, weight in targets.items():
        asset = by_id.get(asset_id)
        if not asset or not asset["allowed"] or not asset["tradable"]:
            spare += weight
            continue
        cap = RISK_POLICY["single_asset_max_weight"]
        if asset["asset_class"] == "equity":
            cap = min(cap, RISK_POLICY["single_stock_max_weight"])
        if asset["asset_class"] == "gold":
            cap = min(cap, RISK_POLICY["gold_max_weight"])
        if asset["asset_class"] == "oil":
            cap = min(cap, RISK_POLICY["oil_max_weight"])
        final_weight = min(weight, cap)
        spare += max(0.0, weight - final_weight)
        if final_weight >= 0.005:
            capped[asset_id] = final_weight

    if spare > 0 and "asset_511880" in capped:
        capped["asset_511880"] += spare * 0.40
        spare *= 0.60
    if spare > 0 and "asset_511010" in capped:
        capped["asset_511010"] = min(
            RISK_POLICY["single_asset_max_weight"],
            capped["asset_511010"] + spare,
        )
    return {asset_id: round(weight, 4) for asset_id, weight in capped.items()}


def current_weight_by_asset(state: dict[str, Any]) -> dict[str, float]:
    return {position["asset_id"]: float(position["weight"]) for position in state["positions"]}


def action_for_diff(diff: float) -> tuple[str, str]:
    if diff > 0.025:
        return "BUY", "买入"
    if diff < -0.025:
        return "SELL", "卖出"
    return "HOLD", "持有"


def action_price(action: str, price: float) -> float:
    if action == "BUY":
        return round(price * 1.005, 4)
    if action == "SELL":
        return round(price * 0.995, 4)
    return round(price, 4)


def stop_take(asset_class: str, action: str, price: float) -> tuple[float, float, int]:
    rule = STOP_RULES.get(asset_class, STOP_RULES["fund"])
    if action == "SELL":
        return 0.0, 0.0, int(rule["holding_days"])
    return (
        round(price * float(rule["stop"]), 4),
        round(price * float(rule["take"]), 4),
        int(rule["holding_days"]),
    )


def build_market_chain(
    snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    profile_name: str,
    risk_score: int,
) -> tuple[str, str, str, str]:
    policy_cn = "政策信号偏积极" if snapshot.get("policy_signal") == "positive" else "政策信号中性"
    policy_en = "policy signal is constructive" if snapshot.get("policy_signal") == "positive" else "policy signal is neutral"
    geo_cn = "地缘风险偏高" if snapshot.get("geopolitics_signal") == "elevated" else "地缘风险可控"
    geo_en = "geopolitical risk is elevated" if snapshot.get("geopolitics_signal") == "elevated" else "geopolitical risk is contained"
    event_titles_cn = "；".join(event["title_cn"] for event in events[:3]) or "暂无新增重大事件"
    event_titles_en = "; ".join(event["title_en"] for event in events[:3]) or "No major new event"
    profile = PROFILE_ALLOCATIONS[profile_name]

    thesis_cn = (
        f"主线：{policy_cn}支撑中国和香港风险资产，但{geo_cn}，组合以"
        f"{profile['name_cn']}档位运行，保留债券、货币和黄金缓冲。"
    )
    thesis_en = (
        f"Main line: {policy_en}, supporting China and Hong Kong risk assets, while "
        f"{geo_en}; the portfolio runs in the {profile['name_en']} profile with bonds, "
        "money-market exposure and gold as buffers."
    )
    chain_cn = (
        f"1. 当日价格：沪深300 {snapshot.get('csi300_change', 0):+.2f}%，"
        f"恒生 {snapshot.get('hsi_change', 0):+.2f}%，标普500 {snapshot.get('sp500_change', 0):+.2f}%。\n"
        f"2. 事件线索：{event_titles_cn}。\n"
        f"3. 传导路径：政策预期改善企业盈利折现率和港股估值；美元兑离岸人民币变化"
        f"{snapshot.get('usdcnh_change', 0):+.2f}%提示汇率压力仍需监控；黄金"
        f"{snapshot.get('gold_change', 0):+.2f}%说明避险需求未消失。\n"
        f"4. 组合动作：风险分数 {risk_score}/100，权益采用核心 ETF + 红利 + 港股修复，"
        "防守端用国债、货币和黄金控制 20% 最大回撤约束。"
    )
    chain_en = (
        f"1. Prices: CSI 300 {snapshot.get('csi300_change', 0):+.2f}%, "
        f"Hang Seng {snapshot.get('hsi_change', 0):+.2f}%, S&P 500 {snapshot.get('sp500_change', 0):+.2f}%.\n"
        f"2. Events: {event_titles_en}.\n"
        f"3. Transmission: policy expectations help earnings discount rates and Hong Kong valuation; "
        f"USD/CNH at {snapshot.get('usdcnh_change', 0):+.2f}% says FX pressure still needs monitoring; "
        f"gold at {snapshot.get('gold_change', 0):+.2f}% shows hedging demand remains.\n"
        f"4. Portfolio action: risk score {risk_score}/100; use core ETFs, dividend exposure and Hong Kong recovery, "
        "while treasury bonds, money-market assets and gold protect the 20% max-drawdown constraint."
    )
    return thesis_cn, thesis_en, chain_cn, chain_en


def build_decision_text(asset: dict[str, Any], action: str, profile_name: str) -> dict[str, str]:
    name_cn = asset["name_cn"]
    name_en = asset["name_en"]
    profile_cn = PROFILE_ALLOCATIONS[profile_name]["name_cn"]
    profile_en = PROFILE_ALLOCATIONS[profile_name]["name_en"]
    if action == "BUY":
        return {
            "trigger_cn": f"{name_cn}满足当前{profile_cn}档位目标仓位，价格不高于建议价时分批买入。",
            "trigger_en": f"{name_en} fits the current {profile_en} target weight; buy in tranches if price is no higher than the suggested limit.",
            "invalidation_cn": "若政策信号转负、指数跌破近20日低点或组合回撤触发预警，本建议失效。",
            "invalidation_en": "Invalid if policy turns negative, the index breaks its 20-day low, or portfolio drawdown warning is triggered.",
            "rationale_cn": f"{name_cn}用于落实目标资产配置，并在不使用杠杆和做空的前提下表达主线判断。",
            "rationale_en": f"{name_en} implements the target allocation and expresses the thesis without leverage or short selling.",
            "risk_note_cn": "按目标仓位控制单一资产风险，成交后由止损价和再评估条件约束。",
            "risk_note_en": "Single-asset risk is capped by target weight; stop-loss and review conditions apply after confirmation.",
        }
    if action == "SELL":
        return {
            "trigger_cn": f"{name_cn}当前权重高于目标仓位，建议降至风控允许区间。",
            "trigger_en": f"{name_en} is above target weight; trim it back into the risk-control band.",
            "invalidation_cn": "若事件确认显著改善且风险分数下降到进取区间，卖出建议需重新评估。",
            "invalidation_en": "Reassess the sell call if events improve materially and risk score moves into the growth zone.",
            "rationale_cn": "卖出不是看空单一资产，而是为了回到组合风险预算。",
            "rationale_en": "The sell action is portfolio risk-budgeting, not a standalone bearish call.",
            "risk_note_cn": "卖出后不建立空头，不做反向投机。",
            "risk_note_en": "No short position or inverse speculation is created after selling.",
        }
    return {
        "trigger_cn": f"{name_cn}已接近目标仓位，等待新的事件触发。",
        "trigger_en": f"{name_en} is close to target weight; wait for new event triggers.",
        "invalidation_cn": "若价格触及止损/止盈或基本面事件改变，重新生成决策。",
        "invalidation_en": "Regenerate the decision if price reaches stop/take levels or fundamentals change.",
        "rationale_cn": "持有可以降低换手和交易成本，符合普通账户约束。",
        "rationale_en": "Holding reduces turnover and transaction cost, consistent with ordinary-account constraints.",
        "risk_note_cn": "继续监控组合回撤、相关性和单一资产上限。",
        "risk_note_en": "Continue monitoring drawdown, correlation and single-asset caps.",
    }


def run_daily_decision() -> dict[str, Any]:
    with connect() as conn:
        snapshot = fetch_latest_snapshot(conn)
        events = fetch_recent_events(conn)
        assets = fetch_assets(conn)
        state = portfolio_state(conn)
        total_value = state["total_value"] or INITIAL_CAPITAL

        risk_score, risk_level = compute_risk_score(snapshot, events)
        profile_name = choose_profile(risk_score)
        targets = target_asset_weights(profile_name, assets)
        current_weights = current_weight_by_asset(state)
        by_id = {asset["id"]: asset for asset in assets}

        thesis_cn, thesis_en, chain_cn, chain_en = build_market_chain(
            snapshot, events, profile_name, risk_score
        )
        confidence = round_confidence(76 - risk_score * 0.18)
        if snapshot.get("source_quality") == "seed_demo":
            confidence = min(confidence, 70)

        report_id = new_id("report")
        created_at = now_iso()
        summary = {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "profile": profile_name,
            "profile_cn": PROFILE_ALLOCATIONS[profile_name]["name_cn"],
            "profile_en": PROFILE_ALLOCATIONS[profile_name]["name_en"],
            "benchmark_comparison": {
                "primary": "CSI300",
                "secondary": "SP500",
                "evaluation": "natural_year_net_return_after_costs",
            },
            "constraints": {
                "max_drawdown_pct": RISK_POLICY["max_drawdown_pct"],
                "no_leverage": True,
                "no_short": True,
                "manual_confirmation": True,
            },
            "data_quality": snapshot.get("source_quality", "unknown"),
            "cash_weight_target": PROFILE_ALLOCATIONS[profile_name]["cash"],
        }

        conn.execute(
            """
            INSERT INTO reports (
                id, created_at, as_of, title_cn, title_en, thesis_cn, thesis_en,
                chain_cn, chain_en, risk_level, regime, confidence, status,
                summary_json, pdf_path, excel_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                created_at,
                date.today().isoformat(),
                "每日模拟投资决策报告",
                "Daily Simulated Investment Decision Report",
                thesis_cn,
                thesis_en,
                chain_cn,
                chain_en,
                risk_level,
                PROFILE_ALLOCATIONS[profile_name]["name_en"],
                confidence,
                "pending_confirmation",
                json_dumps(summary),
                None,
                None,
            ),
        )

        created_decisions = []
        for asset_id, target_weight in targets.items():
            asset = by_id[asset_id]
            current_weight = current_weights.get(asset_id, 0.0)
            diff = target_weight - current_weight
            action, action_cn = action_for_diff(diff)
            if action == "HOLD" and asset_id not in current_weights:
                continue
            local_price = float(asset["price"])
            suggested_price = action_price(action, local_price)
            stop_loss, take_profit, holding_days = stop_take(
                str(asset["asset_class"]), action, suggested_price
            )
            amount_cny = abs(diff) * total_value if action != "HOLD" else 0.0
            text = build_decision_text(asset, action, profile_name)
            asset_score = (
                int(asset["quality_score"]) * 0.25
                + int(asset["momentum_score"]) * 0.25
                + int(asset["valuation_score"]) * 0.20
                + int(asset["liquidity_score"]) * 0.20
                + max(0, 100 - float(asset["volatility_20d"])) * 0.10
            )
            decision_confidence = round_confidence(min(confidence, asset_score))
            decision_id = new_id("decision")
            conn.execute(
                """
                INSERT INTO decisions (
                    id, report_id, created_at, asset_id, symbol, action, action_cn,
                    target_weight, current_weight, amount_cny, price, stop_loss,
                    take_profit, holding_days, confidence, trigger_cn, trigger_en,
                    invalidation_cn, invalidation_en, rationale_cn, rationale_en,
                    risk_note_cn, risk_note_en, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    report_id,
                    created_at,
                    asset_id,
                    asset["symbol"],
                    action,
                    action_cn,
                    target_weight,
                    current_weight,
                    round(amount_cny, 2),
                    suggested_price,
                    stop_loss,
                    take_profit,
                    holding_days,
                    decision_confidence,
                    text["trigger_cn"],
                    text["trigger_en"],
                    text["invalidation_cn"],
                    text["invalidation_en"],
                    text["rationale_cn"],
                    text["rationale_en"],
                    text["risk_note_cn"],
                    text["risk_note_en"],
                    "pending",
                ),
            )
            created_decisions.append(decision_id)

        report = get_report(report_id, conn)
        return report or {"id": report_id, "decisions": created_decisions}


def get_report(report_id: str, conn=None) -> dict[str, Any] | None:
    owns_conn = conn is None
    if conn is None:
        conn = connect()
    try:
        report = row_to_dict(
            conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        )
        if not report:
            return None
        report["summary"] = json.loads(report.get("summary_json") or "{}")
        report["decisions"] = rows_to_dicts(
            conn.execute(
                """
                SELECT d.*, a.name_cn, a.name_en, a.asset_class, a.product_type, a.market,
                       a.region, a.currency
                FROM decisions d
                JOIN assets a ON a.id = d.asset_id
                WHERE d.report_id = ?
                ORDER BY
                    CASE d.action WHEN 'BUY' THEN 1 WHEN 'SELL' THEN 2 ELSE 3 END,
                    d.target_weight DESC
                """,
                (report_id,),
            ).fetchall()
        )
        return report
    finally:
        if owns_conn:
            conn.close()


def latest_report() -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM reports ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return get_report(row["id"], conn)


def list_reports() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, as_of, title_cn, title_en, risk_level, regime, confidence, status FROM reports ORDER BY created_at DESC"
        ).fetchall()
        return rows_to_dicts(rows)


def add_event(payload: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    event = {
        "id": new_id("event"),
        "created_at": now,
        "title_cn": payload.get("title_cn") or payload.get("title") or "手动事件",
        "title_en": payload.get("title_en") or payload.get("title") or "Manual event",
        "source_type": payload.get("source_type", "manual"),
        "region": payload.get("region", "全球"),
        "category": payload.get("category", "event"),
        "severity": int(payload.get("severity", 3)),
        "sentiment": int(payload.get("sentiment", 0)),
        "confidence": int(payload.get("confidence", 60)),
        "link": payload.get("link", ""),
        "is_fact": 1 if payload.get("is_fact", True) else 0,
        "notes_cn": payload.get("notes_cn", ""),
        "notes_en": payload.get("notes_en", ""),
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO events (
                id, created_at, title_cn, title_en, source_type, region, category,
                severity, sentiment, confidence, link, is_fact, notes_cn, notes_en
            )
            VALUES (
                :id, :created_at, :title_cn, :title_en, :source_type, :region, :category,
                :severity, :sentiment, :confidence, :link, :is_fact, :notes_cn, :notes_en
            )
            """,
            event,
        )
    return event


def reject_decision(decision_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        if not row:
            raise ValueError("Decision not found")
        conn.execute(
            "UPDATE decisions SET status = ? WHERE id = ?",
            ("rejected", decision_id),
        )
        return {"id": decision_id, "status": "rejected"}


def confirm_decision(decision_id: str) -> dict[str, Any]:
    with connect() as conn:
        decision = row_to_dict(
            conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
        )
        if not decision:
            raise ValueError("Decision not found")
        if decision["status"] != "pending":
            return {"id": decision_id, "status": decision["status"], "message": "No change"}

        asset = row_to_dict(
            conn.execute("SELECT * FROM assets WHERE id = ?", (decision["asset_id"],)).fetchone()
        )
        if not asset:
            raise ValueError("Asset not found")
        if not int(asset["tradable"]):
            raise ValueError("This asset is simulation-only and cannot be confirmed into the ordinary portfolio")

        action = decision["action"]
        if action == "HOLD":
            conn.execute("UPDATE decisions SET status = ? WHERE id = ?", ("confirmed", decision_id))
            return {"id": decision_id, "status": "confirmed", "message": "Hold confirmed"}

        cash = latest_cash(conn)
        local_price = float(decision["price"])
        fx = currency_to_cny(str(asset["currency"]))
        amount_cny = abs(float(decision["amount_cny"]))
        policy = FEE_POLICY.get(str(asset["asset_class"]), FEE_POLICY["fund"])
        fee = round(amount_cny * float(policy["fee_rate"]), 2)
        slippage = round(amount_cny * float(policy["slippage_rate"]), 2)
        now = now_iso()

        if action == "BUY":
            spendable = max(0.0, cash - RISK_POLICY["cash_min_weight"] * max(cash, INITIAL_CAPITAL))
            gross_amount = min(amount_cny, spendable)
            if gross_amount <= 0:
                raise ValueError("Insufficient simulated cash after minimum cash buffer")
            fee = round(gross_amount * float(policy["fee_rate"]), 2)
            slippage = round(gross_amount * float(policy["slippage_rate"]), 2)
            total_cost = gross_amount + fee + slippage
            if total_cost > cash:
                gross_amount = max(0.0, cash - fee - slippage)
                total_cost = gross_amount + fee + slippage
            quantity = gross_amount / (local_price * fx) if local_price > 0 else 0
            upsert_position(conn, asset, quantity, local_price, "BUY")
            conn.execute(
                """
                INSERT INTO cash_ledger (id, created_at, change_amount, balance_after, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_id("cash"),
                    now,
                    -round(total_cost, 2),
                    round(cash - total_cost, 2),
                    f"Confirmed simulated BUY {asset['symbol']}",
                ),
            )
            order_amount = gross_amount
        elif action == "SELL":
            position = row_to_dict(
                conn.execute(
                    "SELECT * FROM positions WHERE asset_id = ?",
                    (decision["asset_id"],),
                ).fetchone()
            )
            if not position:
                raise ValueError("No simulated position to sell")
            desired_quantity = amount_cny / (local_price * fx) if local_price > 0 else 0
            quantity = min(float(position["quantity"]), desired_quantity)
            order_amount = quantity * local_price * fx
            fee = round(order_amount * float(policy["fee_rate"]), 2)
            slippage = round(order_amount * float(policy["slippage_rate"]), 2)
            proceeds = order_amount - fee - slippage
            upsert_position(conn, asset, -quantity, local_price, "SELL")
            conn.execute(
                """
                INSERT INTO cash_ledger (id, created_at, change_amount, balance_after, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    new_id("cash"),
                    now,
                    round(proceeds, 2),
                    round(cash + proceeds, 2),
                    f"Confirmed simulated SELL {asset['symbol']}",
                ),
            )
        else:
            raise ValueError(f"Unsupported action {action}")

        conn.execute(
            """
            INSERT INTO orders (
                id, decision_id, asset_id, action, quantity, price, amount_cny,
                fee_cny, slippage_cny, status, created_at, confirmed_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("order"),
                decision_id,
                decision["asset_id"],
                action,
                round(quantity, 6),
                local_price,
                round(order_amount, 2),
                fee,
                slippage,
                "simulated_confirmed",
                now,
                now,
                "Simulation only. No real broker order was sent.",
            ),
        )
        conn.execute("UPDATE decisions SET status = ? WHERE id = ?", ("confirmed", decision_id))
        recalc_position_weights(conn)
        write_portfolio_daily(conn)
        return {
            "id": decision_id,
            "status": "confirmed",
            "action": action,
            "quantity": round(quantity, 6),
            "amount_cny": round(order_amount, 2),
            "fee_cny": fee,
            "slippage_cny": slippage,
            "real_order_sent": False,
        }


def upsert_position(conn, asset: dict[str, Any], quantity_change: float, local_price: float, action: str) -> None:
    fx = currency_to_cny(str(asset["currency"]))
    existing = row_to_dict(
        conn.execute("SELECT * FROM positions WHERE asset_id = ?", (asset["id"],)).fetchone()
    )
    now = now_iso()
    if existing:
        old_qty = float(existing["quantity"])
        new_qty = old_qty + quantity_change
        if new_qty <= 1e-8:
            conn.execute("DELETE FROM positions WHERE id = ?", (existing["id"],))
            return
        if action == "BUY":
            avg_cost = ((old_qty * float(existing["avg_cost"])) + (quantity_change * local_price)) / new_qty
        else:
            avg_cost = float(existing["avg_cost"])
        market_value = new_qty * local_price * fx
        conn.execute(
            """
            UPDATE positions
            SET quantity = ?, avg_cost = ?, market_price = ?, market_value = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                new_qty,
                avg_cost,
                local_price,
                market_value,
                now,
                existing["id"],
            ),
        )
    else:
        if quantity_change <= 0:
            return
        market_value = quantity_change * local_price * fx
        conn.execute(
            """
            INSERT INTO positions (
                id, asset_id, quantity, avg_cost, market_price, market_value, weight, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("position"),
                asset["id"],
                quantity_change,
                local_price,
                local_price,
                market_value,
                0.0,
                now,
            ),
        )


def recalc_position_weights(conn) -> None:
    cash = latest_cash(conn)
    rows = rows_to_dicts(conn.execute("SELECT * FROM positions").fetchall())
    position_value = sum(float(row["market_value"]) for row in rows)
    total = cash + position_value
    for row in rows:
        weight = float(row["market_value"]) / total if total else 0.0
        conn.execute("UPDATE positions SET weight = ? WHERE id = ?", (weight, row["id"]))


def write_portfolio_daily(conn) -> None:
    state = portfolio_state(conn)
    total = state["total_value"]
    historical_high = conn.execute(
        "SELECT MAX(portfolio_value) AS high FROM portfolio_daily"
    ).fetchone()["high"]
    high = max(float(historical_high or INITIAL_CAPITAL), total)
    drawdown = (total / high - 1) * 100 if high else 0.0
    return_ytd = (total / INITIAL_CAPITAL - 1) * 100
    as_of = date.today().isoformat()
    conn.execute(
        """
        INSERT OR REPLACE INTO portfolio_daily (
            as_of, portfolio_value, cash_value, positions_value, csi300_equiv,
            sp500_equiv, drawdown_pct, return_ytd_pct
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            as_of,
            round(total, 2),
            round(state["cash"], 2),
            round(state["positions_value"], 2),
            round(INITIAL_CAPITAL * 1.067, 2),
            round(INITIAL_CAPITAL * 1.075, 2),
            round(drawdown, 2),
            round(return_ytd, 2),
        ),
    )


def performance_series() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute("SELECT * FROM portfolio_daily ORDER BY as_of").fetchall()
        )


def benchmark_rows() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM benchmarks ORDER BY id").fetchall())


def event_rows() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM events ORDER BY created_at DESC").fetchall())


def asset_rows(asset_class: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if asset_class:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM assets WHERE asset_class = ? ORDER BY symbol",
                    (asset_class,),
                ).fetchall()
            )
        return fetch_assets(conn)


def stock_rows() -> dict[str, Any]:
    with connect() as conn:
        stocks = rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM assets
                WHERE asset_class = 'equity'
                ORDER BY market, symbol
                """
            ).fetchall()
        )
        stock_events = rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM events
                WHERE category IN ('stock', 'technology', 'market', 'company')
                ORDER BY created_at DESC
                LIMIT 30
                """
            ).fetchall()
        )
    summary: dict[str, Any] = {
        "count": len(stocks),
        "a_share_count": sum(1 for stock in stocks if stock["market"] == "CN"),
        "hk_count": sum(1 for stock in stocks if stock["market"] == "HK"),
        "avg_day_change_pct": round(
            sum(float(stock["day_change_pct"]) for stock in stocks) / len(stocks), 2
        )
        if stocks
        else 0.0,
        "positive_count": sum(1 for stock in stocks if float(stock["day_change_pct"]) > 0),
        "negative_count": sum(1 for stock in stocks if float(stock["day_change_pct"]) < 0),
    }
    return {"summary": summary, "stocks": stocks, "events": stock_events}


REQUIRED_EVENT_CATEGORIES = [
    ("bond", "债券"),
    ("future", "期货"),
    ("fx", "外汇"),
    ("stock", "股票"),
    ("gold", "黄金"),
    ("energy", "能源"),
    ("technology", "科技"),
    ("geopolitics", "地缘"),
    ("macro", "宏观"),
]


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def days_old(value: str | None) -> int | None:
    parsed = parse_day(value)
    if parsed is None:
        return None
    return max(0, (date.today() - parsed).days)


def data_health() -> dict[str, Any]:
    with connect() as conn:
        runs = rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM source_runs
                ORDER BY started_at DESC
                LIMIT 60
                """
            ).fetchall()
        )
        documents_count = int(conn.execute("SELECT COUNT(*) FROM raw_documents").fetchone()[0])
        latest_document = row_to_dict(
            conn.execute(
                "SELECT fetched_at, source, title_cn FROM raw_documents ORDER BY fetched_at DESC LIMIT 1"
            ).fetchone()
        )
        latest_market = row_to_dict(
            conn.execute(
                """
                SELECT MAX(as_of) AS latest_as_of,
                       MAX(fetched_at) AS latest_fetched_at,
                       COUNT(*) AS records,
                       COUNT(DISTINCT symbol) AS symbols
                FROM market_data_history
                """
            ).fetchone()
        ) or {}
        category_rows = rows_to_dicts(
            conn.execute(
                """
                SELECT category, COUNT(*) AS count, MAX(created_at) AS latest_at
                FROM events
                GROUP BY category
                """
            ).fetchall()
        )
        asset_rows_by_class = rows_to_dicts(
            conn.execute(
                """
                SELECT asset_class, COUNT(*) AS count
                FROM assets
                GROUP BY asset_class
                ORDER BY asset_class
                """
            ).fetchall()
        )
        universe_total = int(conn.execute("SELECT COUNT(*) FROM market_universe").fetchone()[0])
        universe_updated_at = row_to_dict(
            conn.execute("SELECT MAX(updated_at) AS updated_at FROM market_universe").fetchone()
        ) or {}
        universe_by_market = rows_to_dicts(
            conn.execute(
                """
                SELECT market, asset_class, COUNT(*) AS count
                FROM market_universe
                GROUP BY market, asset_class
                ORDER BY market, asset_class
                """
            ).fetchall()
        )

    latest_runs: dict[str, dict[str, Any]] = {}
    failure_count = 0
    for run in runs:
        if run["source"] not in latest_runs:
            latest_runs[run["source"]] = run
        if run.get("status") not in {"ok", "success"}:
            failure_count += 1

    category_lookup = {row["category"]: row for row in category_rows}
    coverage = []
    missing_required = 0
    for key, label in REQUIRED_EVENT_CATEGORIES:
        row = category_lookup.get(key, {})
        count = int(row.get("count") or 0)
        if count == 0:
            missing_required += 1
        coverage.append(
            {
                "category": key,
                "label": label,
                "count": count,
                "latest_at": row.get("latest_at", ""),
                "status": "ok" if count else "missing",
            }
        )

    quote_age = days_old(latest_market.get("latest_as_of"))
    document_age = days_old((latest_document or {}).get("fetched_at"))
    universe_age = days_old(universe_updated_at.get("updated_at"))
    score = 100
    if quote_age is None:
        score -= 35
    elif quote_age > 3:
        score -= 35
    elif quote_age > 1:
        score -= 18
    if document_age is None:
        score -= 18
    elif document_age > 7:
        score -= 18
    elif document_age > 2:
        score -= 8
    if universe_total == 0:
        score -= 14
    elif universe_age is not None and universe_age > 7:
        score -= 8
    score -= min(24, missing_required * 4)
    score -= min(18, failure_count * 3)
    score = max(0, min(100, score))

    if score >= 82:
        status = "healthy"
        status_cn = "健康"
    elif score >= 60:
        status = "watch"
        status_cn = "需关注"
    else:
        status = "stale"
        status_cn = "数据偏旧"

    return {
        "status": status,
        "status_cn": status_cn,
        "score": score,
        "market_data": latest_market,
        "latest_document": latest_document,
        "documents_count": documents_count,
        "quote_age_days": quote_age,
        "document_age_days": document_age,
        "universe_age_days": universe_age,
        "latest_runs": list(latest_runs.values()),
        "recent_runs": runs,
        "coverage": coverage,
        "asset_class_counts": asset_rows_by_class,
        "market_universe": {
            "total": universe_total,
            "updated_at": universe_updated_at.get("updated_at"),
            "by_market": universe_by_market,
        },
    }


def stock_detail(symbol: str) -> dict[str, Any] | None:
    normalized = symbol.strip().upper()
    with connect() as conn:
        stock = row_to_dict(
            conn.execute(
                """
                SELECT *
                FROM assets
                WHERE asset_class = 'equity' AND UPPER(symbol) = ?
                LIMIT 1
                """,
                (normalized,),
            ).fetchone()
        )
        if not stock:
            return None
        history = rows_to_dicts(
            conn.execute(
                """
                SELECT as_of, fetched_at, source, price, prev_close, day_change_pct, ytd_return_pct
                FROM market_data_history
                WHERE UPPER(symbol) = ?
                ORDER BY fetched_at DESC
                LIMIT 90
                """,
                (normalized,),
            ).fetchall()
        )
        related_events = rows_to_dicts(
            conn.execute(
                """
                SELECT *
                FROM events
                WHERE category IN ('stock', 'technology', 'market', 'company', 'macro')
                  AND (
                    title_cn LIKE ? OR title_en LIKE ? OR
                    title_cn LIKE ? OR title_en LIKE ?
                  )
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (
                    f"%{stock['symbol']}%",
                    f"%{stock['symbol']}%",
                    f"%{stock['name_cn']}%",
                    f"%{stock['name_en']}%",
                ),
            ).fetchall()
        )
        position = row_to_dict(
            conn.execute(
                """
                SELECT p.*, a.symbol, a.name_cn, a.currency
                FROM positions p
                JOIN assets a ON a.id = p.asset_id
                WHERE a.id = ?
                LIMIT 1
                """,
                (stock["id"],),
            ).fetchone()
        )

    chronological = list(reversed(history))
    latest_price = float(stock.get("price") or 0)
    start_price = float(chronological[0]["price"]) if chronological else latest_price
    history_change_pct = (latest_price / start_price - 1) * 100 if start_price else 0.0
    quality = float(stock.get("quality_score") or 0)
    momentum = float(stock.get("momentum_score") or 0)
    valuation = float(stock.get("valuation_score") or 0)
    liquidity = float(stock.get("liquidity_score") or 0)
    score = round((quality * 0.28 + momentum * 0.25 + valuation * 0.22 + liquidity * 0.25), 1)
    risk_flags = []
    if abs(float(stock.get("day_change_pct") or 0)) >= 3:
        risk_flags.append("单日波动较大")
    if float(stock.get("volatility_20d") or 0) >= 25:
        risk_flags.append("20日波动偏高")
    if not related_events:
        risk_flags.append("近期可归因事件较少")
    if stock.get("market") == "HK":
        risk_flags.append("港币汇率影响人民币估值")

    return {
        "stock": stock,
        "history": chronological,
        "related_events": related_events,
        "position": position,
        "score": score,
        "history_change_pct": round(history_change_pct, 2),
        "risk_flags": risk_flags,
        "view": "可交易观察" if stock.get("tradable") else "仅观察",
    }


def dashboard_view() -> dict[str, Any]:
    with connect() as conn:
        portfolio = portfolio_state(conn)
    report = latest_report()
    performance = performance_series()
    health = data_health()
    stocks = stock_rows()
    events = event_rows()[:12]
    latest_perf = performance[-1] if performance else None
    comparison: dict[str, Any] = {}
    if latest_perf:
        portfolio_return = (float(latest_perf["portfolio_value"]) / INITIAL_CAPITAL - 1) * 100
        csi_return = (float(latest_perf["csi300_equiv"]) / INITIAL_CAPITAL - 1) * 100
        sp_return = (float(latest_perf["sp500_equiv"]) / INITIAL_CAPITAL - 1) * 100
        comparison = {
            "portfolio_return_pct": round(portfolio_return, 2),
            "csi300_return_pct": round(csi_return, 2),
            "sp500_return_pct": round(sp_return, 2),
            "excess_vs_csi300_pct": round(portfolio_return - csi_return, 2),
            "excess_vs_sp500_pct": round(portfolio_return - sp_return, 2),
            "drawdown_pct": latest_perf.get("drawdown_pct", 0),
        }
    return {
        "portfolio": portfolio,
        "report": report,
        "performance": performance,
        "comparison": comparison,
        "data_health": health,
        "stocks": stocks["summary"],
        "events": events,
    }
