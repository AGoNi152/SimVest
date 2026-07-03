from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
EXPORT_DIR = ROOT_DIR / "exports"
STATIC_DIR = ROOT_DIR / "static"
DB_PATH = DATA_DIR / "simvest.sqlite3"

BASE_CURRENCY = "CNY"
INITIAL_CAPITAL = 150_000.0

BENCHMARKS = [
    {
        "id": "CSI300",
        "symbol": "000300.SH",
        "name_cn": "沪深300",
        "name_en": "CSI 300",
        "market": "CN",
        "currency": "CNY",
    },
    {
        "id": "SP500",
        "symbol": "SPX",
        "name_cn": "标普500",
        "name_en": "S&P 500",
        "market": "US",
        "currency": "USD",
    },
]

RISK_POLICY = {
    "base_currency": BASE_CURRENCY,
    "initial_capital": INITIAL_CAPITAL,
    "max_drawdown_pct": 20.0,
    "soft_drawdown_warning_pct": 12.0,
    "single_asset_max_weight": 0.25,
    "single_stock_max_weight": 0.10,
    "single_industry_max_weight": 0.30,
    "single_region_max_weight": 0.70,
    "cash_min_weight": 0.05,
    "gold_max_weight": 0.10,
    "oil_max_weight": 0.05,
    "fx_max_weight": 0.05,
    "bond_min_credit_rating": "AA",
    "short_selling_allowed": False,
    "leverage_allowed": False,
    "real_trading_enabled": False,
    "manual_confirmation_required": True,
    "decision_confidence_step_pct": 5,
}

ASSET_SCOPE = {
    "markets": ["中国大陆", "香港"],
    "benchmarks": ["沪深300", "标普500"],
    "allowed": [
        "A股和港股大中盘股票",
        "股票 ETF",
        "债券和债券 ETF",
        "公募基金和货币基金",
        "G10 外汇观察",
        "黄金和原油相关产品",
        "股指期货仅模拟对冲",
        "远期合约仅模拟定价",
    ],
    "blocked": [
        "真实自动下单",
        "做空",
        "杠杆",
        "ST 股票",
        "亏损股",
        "小盘股",
        "中概股",
        "可转债",
        "裸露衍生品投机",
        "非公开市场产品",
    ],
}

PROFILE_ALLOCATIONS = {
    "conservative": {
        "name_cn": "防守",
        "name_en": "Conservative",
        "cash": 0.12,
        "money": 0.08,
        "bond": 0.35,
        "china_equity": 0.22,
        "hk_equity": 0.10,
        "global_equity": 0.05,
        "gold": 0.08,
        "oil": 0.00,
    },
    "standard": {
        "name_cn": "均衡",
        "name_en": "Balanced",
        "cash": 0.08,
        "money": 0.07,
        "bond": 0.25,
        "china_equity": 0.27,
        "hk_equity": 0.15,
        "global_equity": 0.08,
        "gold": 0.08,
        "oil": 0.02,
    },
    "growth": {
        "name_cn": "进取",
        "name_en": "Growth",
        "cash": 0.06,
        "money": 0.04,
        "bond": 0.16,
        "china_equity": 0.34,
        "hk_equity": 0.20,
        "global_equity": 0.10,
        "gold": 0.06,
        "oil": 0.04,
    },
}

STOP_RULES = {
    "equity": {"stop": 0.92, "take": 1.16, "holding_days": 45},
    "fund": {"stop": 0.92, "take": 1.14, "holding_days": 45},
    "bond": {"stop": 0.985, "take": 1.035, "holding_days": 90},
    "money": {"stop": 0.998, "take": 1.010, "holding_days": 30},
    "gold": {"stop": 0.94, "take": 1.12, "holding_days": 60},
    "oil": {"stop": 0.90, "take": 1.18, "holding_days": 30},
    "fx": {"stop": 0.97, "take": 1.05, "holding_days": 30},
    "future": {"stop": 0.96, "take": 1.08, "holding_days": 10},
    "forward": {"stop": 0.98, "take": 1.04, "holding_days": 90},
}

FEE_POLICY = {
    "equity": {"fee_rate": 0.0010, "slippage_rate": 0.0008},
    "fund": {"fee_rate": 0.0006, "slippage_rate": 0.0005},
    "bond": {"fee_rate": 0.0002, "slippage_rate": 0.0003},
    "money": {"fee_rate": 0.0000, "slippage_rate": 0.0001},
    "gold": {"fee_rate": 0.0008, "slippage_rate": 0.0008},
    "oil": {"fee_rate": 0.0012, "slippage_rate": 0.0015},
    "fx": {"fee_rate": 0.0005, "slippage_rate": 0.0008},
    "future": {"fee_rate": 0.0003, "slippage_rate": 0.0010},
    "forward": {"fee_rate": 0.0005, "slippage_rate": 0.0008},
}

REPORT_TIMEZONE = "Asia/Shanghai"

