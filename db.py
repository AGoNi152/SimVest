from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DB_PATH


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name_cn TEXT NOT NULL,
                name_en TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                product_type TEXT NOT NULL,
                bucket TEXT NOT NULL,
                market TEXT NOT NULL,
                region TEXT NOT NULL,
                currency TEXT NOT NULL,
                price REAL NOT NULL,
                prev_close REAL NOT NULL,
                day_change_pct REAL NOT NULL,
                ytd_return_pct REAL NOT NULL,
                volatility_20d REAL NOT NULL,
                beta REAL NOT NULL,
                liquidity_score INTEGER NOT NULL,
                valuation_score INTEGER NOT NULL,
                momentum_score INTEGER NOT NULL,
                quality_score INTEGER NOT NULL,
                credit_rating TEXT,
                allowed INTEGER NOT NULL,
                tradable INTEGER NOT NULL,
                risk_bucket TEXT NOT NULL,
                notes_cn TEXT NOT NULL,
                notes_en TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS benchmarks (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name_cn TEXT NOT NULL,
                name_en TEXT NOT NULL,
                market TEXT NOT NULL,
                currency TEXT NOT NULL,
                level REAL NOT NULL,
                prev_level REAL NOT NULL,
                day_change_pct REAL NOT NULL,
                ytd_return_pct REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                title_cn TEXT NOT NULL,
                title_en TEXT NOT NULL,
                source_type TEXT NOT NULL,
                region TEXT NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                sentiment INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                link TEXT,
                is_fact INTEGER NOT NULL,
                notes_cn TEXT NOT NULL,
                notes_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_snapshots (
                id TEXT PRIMARY KEY,
                as_of TEXT NOT NULL,
                headline_cn TEXT NOT NULL,
                headline_en TEXT NOT NULL,
                csi300_change REAL NOT NULL,
                sp500_change REAL NOT NULL,
                hsi_change REAL NOT NULL,
                usdcnh_change REAL NOT NULL,
                gold_change REAL NOT NULL,
                oil_change REAL NOT NULL,
                policy_signal TEXT NOT NULL,
                geopolitics_signal TEXT NOT NULL,
                liquidity_signal TEXT NOT NULL,
                source_quality TEXT NOT NULL,
                notes_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS positions (
                id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_cost REAL NOT NULL,
                market_price REAL NOT NULL,
                market_value REAL NOT NULL,
                weight REAL NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            );

            CREATE TABLE IF NOT EXISTS cash_ledger (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                change_amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                reason TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                title_cn TEXT NOT NULL,
                title_en TEXT NOT NULL,
                thesis_cn TEXT NOT NULL,
                thesis_en TEXT NOT NULL,
                chain_cn TEXT NOT NULL,
                chain_en TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                regime TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                status TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                pdf_path TEXT,
                excel_path TEXT
            );

            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                action_cn TEXT NOT NULL,
                target_weight REAL NOT NULL,
                current_weight REAL NOT NULL,
                amount_cny REAL NOT NULL,
                price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                holding_days INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                trigger_cn TEXT NOT NULL,
                trigger_en TEXT NOT NULL,
                invalidation_cn TEXT NOT NULL,
                invalidation_en TEXT NOT NULL,
                rationale_cn TEXT NOT NULL,
                rationale_en TEXT NOT NULL,
                risk_note_cn TEXT NOT NULL,
                risk_note_en TEXT NOT NULL,
                status TEXT NOT NULL,
                FOREIGN KEY(report_id) REFERENCES reports(id),
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                decision_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                amount_cny REAL NOT NULL,
                fee_cny REAL NOT NULL,
                slippage_cny REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                notes TEXT NOT NULL,
                FOREIGN KEY(decision_id) REFERENCES decisions(id),
                FOREIGN KEY(asset_id) REFERENCES assets(id)
            );

            CREATE TABLE IF NOT EXISTS portfolio_daily (
                as_of TEXT PRIMARY KEY,
                portfolio_value REAL NOT NULL,
                cash_value REAL NOT NULL,
                positions_value REAL NOT NULL,
                csi300_equiv REAL NOT NULL,
                sp500_equiv REAL NOT NULL,
                drawdown_pct REAL NOT NULL,
                return_ytd_pct REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_runs (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                records INTEGER NOT NULL,
                error TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS raw_documents (
                id TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title_cn TEXT NOT NULL,
                title_en TEXT NOT NULL,
                published_at TEXT NOT NULL,
                region TEXT NOT NULL,
                category TEXT NOT NULL,
                severity INTEGER NOT NULL,
                sentiment INTEGER NOT NULL,
                confidence INTEGER NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_data_history (
                id TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                asset_id TEXT,
                symbol TEXT NOT NULL,
                source TEXT NOT NULL,
                price REAL NOT NULL,
                prev_close REAL NOT NULL,
                day_change_pct REAL NOT NULL,
                ytd_return_pct REAL NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ai_advice (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                advice_text TEXT NOT NULL,
                context_json TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                error TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS expert_debate_reports (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                as_of TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                prompts_json TEXT NOT NULL,
                expert_outputs_json TEXT NOT NULL,
                final_report_md TEXT NOT NULL,
                context_json TEXT NOT NULL,
                markdown_path TEXT,
                pdf_path TEXT,
                excel_path TEXT,
                error TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_universe (
                symbol TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                name_cn TEXT NOT NULL,
                name_en TEXT NOT NULL,
                market TEXT NOT NULL,
                region TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                product_type TEXT NOT NULL,
                sector TEXT NOT NULL,
                board TEXT NOT NULL,
                currency TEXT NOT NULL,
                price REAL,
                prev_close REAL,
                day_change_pct REAL,
                change_value REAL,
                volume REAL,
                turnover REAL,
                turnover_rate REAL,
                amplitude REAL,
                high REAL,
                low REAL,
                open_price REAL,
                market_cap REAL,
                float_market_cap REAL,
                pe_ttm REAL,
                pb REAL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                tradable INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS market_universe_history (
                id TEXT PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                product_type TEXT NOT NULL,
                price REAL,
                prev_close REAL,
                day_change_pct REAL,
                turnover REAL,
                source TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_market_universe_market
                ON market_universe(market, asset_class, product_type);
            CREATE INDEX IF NOT EXISTS idx_market_universe_sector
                ON market_universe(sector);
            CREATE INDEX IF NOT EXISTS idx_market_universe_turnover
                ON market_universe(turnover);
            CREATE INDEX IF NOT EXISTS idx_market_universe_history_symbol
                ON market_universe_history(symbol, fetched_at);
            """
        )


def latest_cash_balance(conn: sqlite3.Connection | None = None) -> float:
    owns_conn = conn is None
    if conn is None:
        conn = connect()
    try:
        row = conn.execute(
            "SELECT balance_after FROM cash_ledger ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return float(row["balance_after"]) if row else 0.0
    finally:
        if owns_conn:
            conn.close()


def db_file_exists() -> bool:
    return Path(DB_PATH).exists()
