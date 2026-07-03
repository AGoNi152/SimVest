from __future__ import annotations

from datetime import date

from .config import BENCHMARKS, INITIAL_CAPITAL, RISK_POLICY
from .db import connect, json_dumps, new_id, now_iso


def seed_if_empty() -> None:
    with connect() as conn:
        asset_count = conn.execute("SELECT COUNT(*) AS count FROM assets").fetchone()["count"]
        if asset_count:
            ensure_expanded_universe()
            return

        now = now_iso()
        assets = [
            {
                "id": "asset_510300",
                "symbol": "510300.SH",
                "name_cn": "沪深300ETF",
                "name_en": "CSI 300 ETF",
                "asset_class": "fund",
                "product_type": "ETF",
                "bucket": "china_equity",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 3.78,
                "prev_close": 3.74,
                "day_change_pct": 1.07,
                "ytd_return_pct": 6.8,
                "volatility_20d": 16.2,
                "beta": 1.00,
                "liquidity_score": 95,
                "valuation_score": 72,
                "momentum_score": 66,
                "quality_score": 78,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "core",
                "notes_cn": "核心权益仓位，适合跟踪沪深300。",
                "notes_en": "Core China equity sleeve tracking CSI 300.",
            },
            {
                "id": "asset_510880",
                "symbol": "510880.SH",
                "name_cn": "红利ETF",
                "name_en": "China Dividend ETF",
                "asset_class": "fund",
                "product_type": "ETF",
                "bucket": "china_equity",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 3.12,
                "prev_close": 3.10,
                "day_change_pct": 0.65,
                "ytd_return_pct": 8.1,
                "volatility_20d": 12.8,
                "beta": 0.78,
                "liquidity_score": 90,
                "valuation_score": 80,
                "momentum_score": 69,
                "quality_score": 74,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "defensive_equity",
                "notes_cn": "高股息风格，用于降低权益组合波动。",
                "notes_en": "Dividend style exposure to reduce equity volatility.",
            },
            {
                "id": "asset_159920",
                "symbol": "159920.SZ",
                "name_cn": "恒生ETF",
                "name_en": "Hang Seng ETF",
                "asset_class": "fund",
                "product_type": "ETF",
                "bucket": "hk_equity",
                "market": "HK",
                "region": "香港",
                "currency": "CNY",
                "price": 1.24,
                "prev_close": 1.22,
                "day_change_pct": 1.64,
                "ytd_return_pct": 10.3,
                "volatility_20d": 20.4,
                "beta": 1.10,
                "liquidity_score": 88,
                "valuation_score": 76,
                "momentum_score": 71,
                "quality_score": 70,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "satellite_equity",
                "notes_cn": "香港权益核心敞口，适合表达港股估值修复。",
                "notes_en": "Core Hong Kong equity sleeve for valuation recovery exposure.",
            },
            {
                "id": "asset_513500",
                "symbol": "513500.SH",
                "name_cn": "标普500ETF",
                "name_en": "S&P 500 ETF",
                "asset_class": "fund",
                "product_type": "QDII ETF",
                "bucket": "global_equity",
                "market": "CN",
                "region": "美国",
                "currency": "CNY",
                "price": 2.05,
                "prev_close": 2.04,
                "day_change_pct": 0.49,
                "ytd_return_pct": 7.6,
                "volatility_20d": 15.1,
                "beta": 0.92,
                "liquidity_score": 83,
                "valuation_score": 55,
                "momentum_score": 73,
                "quality_score": 82,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "global_diversifier",
                "notes_cn": "用于和标普500基准保持可比，同时分散中国资产风险。",
                "notes_en": "Keeps the portfolio comparable with S&P 500 and diversifies China exposure.",
            },
            {
                "id": "asset_511010",
                "symbol": "511010.SH",
                "name_cn": "国债ETF",
                "name_en": "China Treasury Bond ETF",
                "asset_class": "bond",
                "product_type": "Bond ETF",
                "bucket": "bond",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 126.40,
                "prev_close": 126.18,
                "day_change_pct": 0.17,
                "ytd_return_pct": 2.2,
                "volatility_20d": 3.0,
                "beta": -0.12,
                "liquidity_score": 82,
                "valuation_score": 68,
                "momentum_score": 61,
                "quality_score": 90,
                "credit_rating": "AAA",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "defense",
                "notes_cn": "防守仓位和组合波动缓冲。",
                "notes_en": "Defensive allocation and volatility buffer.",
            },
            {
                "id": "asset_511880",
                "symbol": "511880.SH",
                "name_cn": "货币ETF",
                "name_en": "Money Market ETF",
                "asset_class": "money",
                "product_type": "Money ETF",
                "bucket": "money",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 100.02,
                "prev_close": 100.01,
                "day_change_pct": 0.01,
                "ytd_return_pct": 0.9,
                "volatility_20d": 0.3,
                "beta": 0.00,
                "liquidity_score": 92,
                "valuation_score": 65,
                "momentum_score": 50,
                "quality_score": 88,
                "credit_rating": "AAA",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "cash_plus",
                "notes_cn": "替代现金，用于等待机会和降低回撤。",
                "notes_en": "Cash alternative used for dry powder and drawdown control.",
            },
            {
                "id": "asset_518880",
                "symbol": "518880.SH",
                "name_cn": "黄金ETF",
                "name_en": "Gold ETF",
                "asset_class": "gold",
                "product_type": "Commodity ETF",
                "bucket": "gold",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 5.48,
                "prev_close": 5.42,
                "day_change_pct": 1.11,
                "ytd_return_pct": 12.4,
                "volatility_20d": 13.9,
                "beta": 0.10,
                "liquidity_score": 94,
                "valuation_score": 60,
                "momentum_score": 77,
                "quality_score": 76,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "hedge",
                "notes_cn": "地缘政治和实际利率冲击的对冲资产，上限 10%。",
                "notes_en": "Hedge against geopolitical and real-rate shocks, capped at 10%.",
            },
            {
                "id": "asset_162411",
                "symbol": "162411.SZ",
                "name_cn": "油气LOF",
                "name_en": "Oil & Gas Fund",
                "asset_class": "oil",
                "product_type": "LOF",
                "bucket": "oil",
                "market": "CN",
                "region": "全球",
                "currency": "CNY",
                "price": 0.86,
                "prev_close": 0.85,
                "day_change_pct": 1.18,
                "ytd_return_pct": 3.2,
                "volatility_20d": 27.5,
                "beta": 0.55,
                "liquidity_score": 66,
                "valuation_score": 58,
                "momentum_score": 62,
                "quality_score": 50,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "tactical",
                "notes_cn": "仅作为原油主题的小比例战术仓位，上限 5%。",
                "notes_en": "Small tactical oil sleeve only, capped at 5%.",
            },
            {
                "id": "asset_0700hk",
                "symbol": "0700.HK",
                "name_cn": "腾讯控股",
                "name_en": "Tencent Holdings",
                "asset_class": "equity",
                "product_type": "Stock",
                "bucket": "hk_equity",
                "market": "HK",
                "region": "香港",
                "currency": "HKD",
                "price": 385.00,
                "prev_close": 380.00,
                "day_change_pct": 1.32,
                "ytd_return_pct": 9.4,
                "volatility_20d": 24.0,
                "beta": 1.15,
                "liquidity_score": 96,
                "valuation_score": 70,
                "momentum_score": 67,
                "quality_score": 88,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 1,
                "risk_bucket": "single_stock",
                "notes_cn": "大盘盈利质量股票，单票仓位上限 10%。",
                "notes_en": "Large-cap quality stock, capped at 10% single-name weight.",
            },
            {
                "id": "asset_ifhedge",
                "symbol": "IF.CFE",
                "name_cn": "沪深300股指期货模拟对冲",
                "name_en": "CSI 300 Futures Hedge Simulation",
                "asset_class": "future",
                "product_type": "Index Future",
                "bucket": "hedge_future",
                "market": "CN",
                "region": "中国大陆",
                "currency": "CNY",
                "price": 3850.00,
                "prev_close": 3820.00,
                "day_change_pct": 0.79,
                "ytd_return_pct": 6.5,
                "volatility_20d": 18.0,
                "beta": -1.00,
                "liquidity_score": 85,
                "valuation_score": 50,
                "momentum_score": 55,
                "quality_score": 50,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 0,
                "risk_bucket": "simulation_only",
                "notes_cn": "仅用于压力测试和对冲建议，不进入普通人模拟组合。",
                "notes_en": "Used for stress testing and hedge advice only, excluded from ordinary portfolio.",
            },
            {
                "id": "asset_usdcnh3m",
                "symbol": "USD/CNH-3M-FWD",
                "name_cn": "美元兑离岸人民币3个月远期模拟",
                "name_en": "USD/CNH 3M Forward Simulation",
                "asset_class": "forward",
                "product_type": "FX Forward",
                "bucket": "fx",
                "market": "OTC",
                "region": "全球",
                "currency": "CNY",
                "price": 7.28,
                "prev_close": 7.26,
                "day_change_pct": 0.28,
                "ytd_return_pct": 1.4,
                "volatility_20d": 5.5,
                "beta": 0.20,
                "liquidity_score": 70,
                "valuation_score": 52,
                "momentum_score": 60,
                "quality_score": 60,
                "credit_rating": "",
                "allowed": 1,
                "tradable": 0,
                "risk_bucket": "simulation_only",
                "notes_cn": "仅用于远期定价和汇率风险观察。",
                "notes_en": "Used only for forward pricing and currency-risk monitoring.",
            },
        ]

        conn.executemany(
            """
            INSERT INTO assets (
                id, symbol, name_cn, name_en, asset_class, product_type, bucket, market,
                region, currency, price, prev_close, day_change_pct, ytd_return_pct,
                volatility_20d, beta, liquidity_score, valuation_score, momentum_score,
                quality_score, credit_rating, allowed, tradable, risk_bucket, notes_cn,
                notes_en, updated_at
            )
            VALUES (
                :id, :symbol, :name_cn, :name_en, :asset_class, :product_type, :bucket, :market,
                :region, :currency, :price, :prev_close, :day_change_pct, :ytd_return_pct,
                :volatility_20d, :beta, :liquidity_score, :valuation_score, :momentum_score,
                :quality_score, :credit_rating, :allowed, :tradable, :risk_bucket, :notes_cn,
                :notes_en, :updated_at
            )
            """,
            [{**asset, "updated_at": now} for asset in assets],
        )

        benchmark_rows = [
            {
                **BENCHMARKS[0],
                "level": 3850.0,
                "prev_level": 3815.0,
                "day_change_pct": 0.92,
                "ytd_return_pct": 6.7,
                "updated_at": now,
            },
            {
                **BENCHMARKS[1],
                "level": 5480.0,
                "prev_level": 5452.0,
                "day_change_pct": 0.51,
                "ytd_return_pct": 7.5,
                "updated_at": now,
            },
        ]
        conn.executemany(
            """
            INSERT INTO benchmarks (
                id, symbol, name_cn, name_en, market, currency, level, prev_level,
                day_change_pct, ytd_return_pct, updated_at
            )
            VALUES (
                :id, :symbol, :name_cn, :name_en, :market, :currency, :level, :prev_level,
                :day_change_pct, :ytd_return_pct, :updated_at
            )
            """,
            benchmark_rows,
        )

        events = [
            {
                "id": new_id("event"),
                "created_at": now,
                "title_cn": "内地稳增长政策预期升温，港股风险偏好修复",
                "title_en": "China growth-support expectations improve Hong Kong risk appetite",
                "source_type": "manual_seed",
                "region": "中国大陆/香港",
                "category": "policy",
                "severity": 3,
                "sentiment": 1,
                "confidence": 70,
                "link": "",
                "is_fact": 0,
                "notes_cn": "示例事件：用于演示政策线索如何转化为权益仓位。",
                "notes_en": "Seed event showing how policy cues translate into equity allocation.",
            },
            {
                "id": new_id("event"),
                "created_at": now,
                "title_cn": "中东风险维持，黄金维持组合对冲价值",
                "title_en": "Middle East risk keeps gold useful as a portfolio hedge",
                "source_type": "manual_seed",
                "region": "中东",
                "category": "geopolitics",
                "severity": 4,
                "sentiment": -1,
                "confidence": 65,
                "link": "",
                "is_fact": 0,
                "notes_cn": "示例事件：用于演示地缘风险对黄金仓位的影响。",
                "notes_en": "Seed event showing geopolitical risk impact on gold allocation.",
            },
        ]
        conn.executemany(
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
            events,
        )

        snapshot = {
            "id": new_id("snapshot"),
            "as_of": date.today().isoformat(),
            "headline_cn": "政策预期托底中国资产，地缘风险抬升黄金对冲需求。",
            "headline_en": "Policy expectations support China assets while geopolitical risk lifts gold hedge demand.",
            "csi300_change": 0.92,
            "sp500_change": 0.51,
            "hsi_change": 1.34,
            "usdcnh_change": 0.28,
            "gold_change": 1.11,
            "oil_change": 1.18,
            "policy_signal": "positive",
            "geopolitics_signal": "elevated",
            "liquidity_signal": "neutral",
            "source_quality": "seed_demo",
            "notes_json": json_dumps(
                {
                    "cn": "这是内置示例快照。接入免费数据源后应替换为每日真实快照。",
                    "en": "Seed demo snapshot. Replace with daily live snapshots after data adapters are connected.",
                }
            ),
        }
        conn.execute(
            """
            INSERT INTO market_snapshots (
                id, as_of, headline_cn, headline_en, csi300_change, sp500_change,
                hsi_change, usdcnh_change, gold_change, oil_change, policy_signal,
                geopolitics_signal, liquidity_signal, source_quality, notes_json
            )
            VALUES (
                :id, :as_of, :headline_cn, :headline_en, :csi300_change, :sp500_change,
                :hsi_change, :usdcnh_change, :gold_change, :oil_change, :policy_signal,
                :geopolitics_signal, :liquidity_signal, :source_quality, :notes_json
            )
            """,
            snapshot,
        )

        conn.execute(
            """
            INSERT INTO cash_ledger (id, created_at, change_amount, balance_after, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                new_id("cash"),
                now,
                INITIAL_CAPITAL,
                INITIAL_CAPITAL,
                "Initial simulated capital / 初始模拟资金",
            ),
        )

        conn.execute(
            """
            INSERT INTO portfolio_daily (
                as_of, portfolio_value, cash_value, positions_value, csi300_equiv,
                sp500_equiv, drawdown_pct, return_ytd_pct
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                date.today().isoformat(),
                INITIAL_CAPITAL,
                INITIAL_CAPITAL,
                0.0,
                INITIAL_CAPITAL,
                INITIAL_CAPITAL,
                0.0,
                0.0,
            ),
        )

        conn.execute(
            "INSERT INTO user_config (key, value) VALUES (?, ?)",
            ("risk_policy", json_dumps(RISK_POLICY)),
        )
    ensure_expanded_universe()


def ensure_expanded_universe() -> None:
    now = now_iso()
    extra_assets = [
        make_asset("asset_511260", "511260.SH", "十年国债ETF", "10Y China Treasury ETF", "bond", "Bond ETF", "bond", "CN", "中国大陆", "CNY", 116.0, 116.0, "AAA", 1, 1, "duration", "中长期利率和债券久期观察。", "Duration and bond-rate exposure."),
        make_asset("asset_511030", "511030.SH", "公司债ETF", "China Corporate Bond ETF", "bond", "Bond ETF", "bond", "CN", "中国大陆", "CNY", 110.0, 110.0, "AAA", 1, 1, "credit", "信用债和信用利差观察。", "Corporate bond and credit-spread exposure."),
        make_asset("asset_513180", "513180.SH", "恒生科技ETF", "Hang Seng Tech ETF", "fund", "ETF", "hk_equity", "HK", "香港", "CNY", 0.62, 0.62, "", 1, 1, "technology_equity", "港股科技板块敞口。", "Hong Kong technology equity exposure."),
        make_asset("asset_512760", "512760.SH", "芯片ETF", "China Semiconductor ETF", "fund", "ETF", "china_equity", "CN", "中国大陆", "CNY", 1.02, 1.02, "", 1, 1, "technology_equity", "A股半导体和科技周期观察。", "China semiconductor and technology-cycle exposure."),
        make_asset("asset_9988hk", "9988.HK", "阿里巴巴-W", "Alibaba Group Holding", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 78.0, 78.0, "", 1, 1, "single_stock", "港股互联网和消费科技观察。", "Hong Kong internet and consumer-tech exposure."),
        make_asset("asset_600519", "600519.SH", "贵州茅台", "Kweichow Moutai", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 1500.0, 1500.0, "", 1, 1, "single_stock", "A股消费龙头，观察内需和高端消费。", "A-share consumer leader for domestic-demand monitoring."),
        make_asset("asset_601318", "601318.SH", "中国平安", "Ping An Insurance", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 50.0, 50.0, "", 1, 1, "single_stock", "保险和金融周期观察。", "Insurance and financial-cycle exposure."),
        make_asset("asset_600036", "600036.SH", "招商银行", "China Merchants Bank", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 40.0, 40.0, "", 1, 1, "single_stock", "银行资产质量和利率周期观察。", "Bank asset-quality and rate-cycle exposure."),
        make_asset("asset_300750", "300750.SZ", "宁德时代", "CATL", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 210.0, 210.0, "", 1, 1, "single_stock", "新能源和制造业景气观察。", "New-energy and manufacturing-cycle exposure."),
        make_asset("asset_000333", "000333.SZ", "美的集团", "Midea Group", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 70.0, 70.0, "", 1, 1, "single_stock", "家电、出口和消费升级观察。", "Home-appliance, export and consumption-upgrade exposure."),
        make_asset("asset_002475", "002475.SZ", "立讯精密", "Luxshare Precision", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 38.0, 38.0, "", 1, 1, "single_stock", "消费电子和苹果产业链观察。", "Consumer electronics and Apple supply-chain exposure."),
        make_asset("asset_600276", "600276.SH", "恒瑞医药", "Hengrui Medicine", "equity", "Stock", "china_equity", "CN", "中国大陆", "CNY", 45.0, 45.0, "", 1, 1, "single_stock", "创新药和医药政策观察。", "Innovative-drug and healthcare-policy exposure."),
        make_asset("asset_1299hk", "1299.HK", "友邦保险", "AIA Group", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 60.0, 60.0, "", 1, 1, "single_stock", "港股保险和亚洲消费金融观察。", "Hong Kong insurance and Asian consumer-finance exposure."),
        make_asset("asset_3690hk", "3690.HK", "美团-W", "Meituan", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 120.0, 120.0, "", 1, 1, "single_stock", "本地生活、平台经济和消费科技观察。", "Local services, platform economy and consumer-tech exposure."),
        make_asset("asset_0005hk", "0005.HK", "汇丰控股", "HSBC Holdings", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 70.0, 70.0, "", 1, 1, "single_stock", "全球利率、美元和香港金融股观察。", "Global rates, dollar and Hong Kong financial-stock exposure."),
        make_asset("asset_2318hk", "2318.HK", "中国平安-H", "Ping An Insurance H", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 40.0, 40.0, "", 1, 1, "single_stock", "H股金融和估值折价观察。", "H-share financial and valuation-discount exposure."),
        make_asset("asset_1810hk", "1810.HK", "小米集团-W", "Xiaomi", "equity", "Stock", "hk_equity", "HK", "香港", "HKD", 20.0, 20.0, "", 1, 1, "single_stock", "智能硬件、汽车和消费电子观察。", "Smart hardware, EV and consumer-electronics exposure."),
        make_asset("asset_159934", "159934.SZ", "黄金ETF", "Gold ETF SZ", "gold", "Commodity ETF", "gold", "CN", "中国大陆", "CNY", 6.0, 6.0, "", 1, 1, "hedge", "黄金资产补充观察。", "Additional gold exposure."),
        make_asset("asset_159930", "159930.SZ", "能源ETF", "China Energy ETF", "oil", "ETF", "oil", "CN", "中国大陆", "CNY", 1.10, 1.10, "", 1, 1, "energy_equity", "能源产业链和油价传导观察。", "Energy-sector and oil-price transmission exposure."),
        make_asset("asset_usdcnh_spot", "USD/CNH", "美元兑离岸人民币", "USD/CNH Spot", "fx", "FX Spot", "fx", "FX", "全球", "CNY", 7.25, 7.25, "", 1, 0, "currency_watch", "外汇风险观察，不进入普通模拟组合。", "Currency-risk watch only, not tradable in the ordinary portfolio."),
        make_asset("asset_eurusd", "EUR/USD", "欧元兑美元", "EUR/USD Spot", "fx", "FX Spot", "fx", "FX", "全球", "USD", 1.08, 1.08, "", 1, 0, "currency_watch", "G10外汇观察。", "G10 currency watch."),
        make_asset("asset_usdjpy", "USD/JPY", "美元兑日元", "USD/JPY Spot", "fx", "FX Spot", "fx", "FX", "全球", "JPY", 155.0, 155.0, "", 1, 0, "currency_watch", "美元流动性和套息交易观察。", "Dollar liquidity and carry-trade watch."),
        make_asset("asset_tbond_future", "T.CFE", "十年国债期货模拟", "10Y Treasury Futures Simulation", "future", "Bond Future", "hedge_future", "CN", "中国大陆", "CNY", 102.0, 102.0, "", 1, 0, "simulation_only", "仅用于债券期货对冲和利率压力测试。", "Bond futures hedge and rate stress testing only."),
        make_asset("asset_aufuture", "GC=F", "黄金期货模拟", "Gold Futures Simulation", "future", "Commodity Future", "hedge_future", "GLOBAL", "全球", "USD", 2300.0, 2300.0, "", 1, 0, "simulation_only", "仅用于黄金期货风险观察。", "Gold futures risk watch only."),
        make_asset("asset_oilfuture", "CL=F", "原油期货模拟", "Crude Oil Futures Simulation", "future", "Commodity Future", "hedge_future", "GLOBAL", "全球", "USD", 75.0, 75.0, "", 1, 0, "simulation_only", "仅用于原油期货风险观察。", "Crude oil futures risk watch only."),
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO assets (
                id, symbol, name_cn, name_en, asset_class, product_type, bucket, market,
                region, currency, price, prev_close, day_change_pct, ytd_return_pct,
                volatility_20d, beta, liquidity_score, valuation_score, momentum_score,
                quality_score, credit_rating, allowed, tradable, risk_bucket, notes_cn,
                notes_en, updated_at
            )
            VALUES (
                :id, :symbol, :name_cn, :name_en, :asset_class, :product_type, :bucket, :market,
                :region, :currency, :price, :prev_close, :day_change_pct, :ytd_return_pct,
                :volatility_20d, :beta, :liquidity_score, :valuation_score, :momentum_score,
                :quality_score, :credit_rating, :allowed, :tradable, :risk_bucket, :notes_cn,
                :notes_en, :updated_at
            )
            """,
            [{**asset, "updated_at": now} for asset in extra_assets],
        )


def make_asset(
    asset_id: str,
    symbol: str,
    name_cn: str,
    name_en: str,
    asset_class: str,
    product_type: str,
    bucket: str,
    market: str,
    region: str,
    currency: str,
    price: float,
    prev_close: float,
    credit_rating: str,
    allowed: int,
    tradable: int,
    risk_bucket: str,
    notes_cn: str,
    notes_en: str,
) -> dict:
    return {
        "id": asset_id,
        "symbol": symbol,
        "name_cn": name_cn,
        "name_en": name_en,
        "asset_class": asset_class,
        "product_type": product_type,
        "bucket": bucket,
        "market": market,
        "region": region,
        "currency": currency,
        "price": price,
        "prev_close": prev_close,
        "day_change_pct": 0.0,
        "ytd_return_pct": 0.0,
        "volatility_20d": 18.0 if asset_class in {"equity", "fund", "future", "oil"} else 6.0,
        "beta": 1.0 if asset_class in {"equity", "fund"} else 0.2,
        "liquidity_score": 75,
        "valuation_score": 60,
        "momentum_score": 55,
        "quality_score": 65,
        "credit_rating": credit_rating,
        "allowed": allowed,
        "tradable": tradable,
        "risk_bucket": risk_bucket,
        "notes_cn": notes_cn,
        "notes_en": notes_en,
    }
