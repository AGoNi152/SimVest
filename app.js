const state = {
  config: null,
  dashboard: null,
  portfolio: null,
  report: null,
  stocks: { summary: {}, stocks: [], events: [] },
  stockDetail: null,
  selectedStockSymbol: "",
  stockQuery: "",
  aiAdvice: null,
  expertReport: null,
  assets: [],
  events: [],
  performance: [],
  dataHealth: null,
  sourceRuns: [],
  rawDocuments: [],
  universeSummary: null,
  universeRows: [],
  universeTotal: 0,
  universeOffset: 0,
  universeLimit: 100,
  universeFilters: {
    search: "",
    market: "",
    asset_class: "",
    sort: "turnover",
    direction: "desc",
  },
};

const fmtCny = new Intl.NumberFormat("zh-CN", {
  style: "currency",
  currency: "CNY",
  maximumFractionDigits: 0,
});

const fmtNum = new Intl.NumberFormat("zh-CN", {
  maximumFractionDigits: 2,
});

function asNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function pctWeight(value) {
  return `${(asNumber(value) * 100).toFixed(1)}%`;
}

function pctPoint(value, digits = 2) {
  const number = asNumber(value);
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}%`;
}

function plainPct(value, digits = 2) {
  return `${asNumber(value).toFixed(digits)}%`;
}

function money(value) {
  return fmtCny.format(asNumber(value));
}

function largeNumber(value) {
  const number = asNumber(value);
  if (Math.abs(number) >= 100000000) return `${(number / 100000000).toFixed(2)}亿`;
  if (Math.abs(number) >= 10000) return `${(number / 10000).toFixed(2)}万`;
  return fmtNum.format(number);
}

function largeMoney(value) {
  if (value === null || value === undefined || value === "") return "--";
  return `${largeNumber(value)}`;
}

function formatOptional(value) {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) return "--";
  return fmtNum.format(asNumber(value));
}

function signedMoney(value) {
  const number = asNumber(value);
  return `${number >= 0 ? "+" : ""}${money(number)}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || data.message || "请求失败");
  }
  return data;
}

async function loadAll() {
  const [
    config,
    dashboard,
    stocks,
    aiAdvice,
    expertReport,
    assets,
    events,
    performance,
    health,
    runs,
    documents,
    universeSummaryData,
    universeData,
  ] = await Promise.all([
    api("/api/config"),
    api("/api/dashboard"),
    api("/api/stocks"),
    api("/api/ai/advice/latest"),
    api("/api/expert-debate/latest"),
    api("/api/assets"),
    api("/api/events"),
    api("/api/performance"),
    api("/api/data/health"),
    api("/api/data/runs"),
    api("/api/data/documents"),
    api("/api/universe/summary"),
    fetchUniversePage(false),
  ]);

  state.config = config;
  state.dashboard = dashboard;
  state.portfolio = dashboard.portfolio;
  state.report = dashboard.report;
  state.stocks = stocks;
  state.aiAdvice = aiAdvice.advice;
  state.expertReport = expertReport.report;
  state.assets = assets.assets || [];
  state.events = events.events || [];
  state.performance = performance.series || dashboard.performance || [];
  state.dataHealth = health.health || dashboard.data_health;
  state.sourceRuns = runs.runs || [];
  state.rawDocuments = documents.documents || [];
  state.universeSummary = universeSummaryData.summary;
  state.universeRows = universeData.rows || [];
  state.universeTotal = universeData.total || 0;
  state.universeOffset = universeData.offset || 0;
  state.universeLimit = universeData.limit || state.universeLimit;

  if (!state.selectedStockSymbol && state.stocks.stocks.length) {
    state.selectedStockSymbol = state.stocks.stocks[0].symbol;
  }
  if (state.selectedStockSymbol) {
    await loadStockDetail(state.selectedStockSymbol, false);
  }
  render();
}

async function loadStockDetail(symbol, shouldRender = true) {
  state.selectedStockSymbol = symbol;
  state.stockDetail = await api(`/api/stocks/${encodeURIComponent(symbol)}`);
  if (shouldRender) {
    renderStocks();
  }
}

function render() {
  renderDashboard();
  renderPerformance();
  renderPositions();
  renderReport();
  renderAiAdvice();
  renderExpertDebate();
  renderDecisions();
  renderStocks();
  renderDataHealth();
  renderEvents();
  renderUniverse();
  renderAssets();
  renderRisk();
}

function universeQuery() {
  const params = new URLSearchParams();
  params.set("limit", String(state.universeLimit));
  params.set("offset", String(state.universeOffset));
  params.set("sort", state.universeFilters.sort || "turnover");
  params.set("direction", state.universeFilters.direction || "desc");
  for (const key of ["search", "market", "asset_class"]) {
    if (state.universeFilters[key]) params.set(key, state.universeFilters[key]);
  }
  return params.toString();
}

async function fetchUniversePage(applyState = true) {
  const data = await api(`/api/universe?${universeQuery()}`);
  if (applyState) {
    state.universeRows = data.rows || [];
    state.universeTotal = data.total || 0;
    state.universeOffset = data.offset || 0;
    state.universeLimit = data.limit || state.universeLimit;
    renderUniverse();
  }
  return data;
}

function renderDashboard() {
  const portfolio = state.portfolio || {};
  const report = state.report || {};
  const health = state.dataHealth || {};
  const comparison = (state.dashboard && state.dashboard.comparison) || {};
  const pnl = asNumber(portfolio.total_pnl);
  const pnlPct = asNumber(portfolio.total_pnl_pct);

  setText("#dashboardThesis", report.thesis_cn || "等待生成今日市场主线");
  document.querySelector("#dashboardBadges").innerHTML = [
    chip(`数据：${health.status_cn || "未知"}`, health.status === "healthy" ? "good" : health.status === "stale" ? "bad" : "warn"),
    chip(`风控：${report.risk_level || "未生成"}`, "neutral"),
    chip(`现金：${pctWeight(portfolio.cash_weight || 0)}`, "neutral"),
  ].join("");

  document.querySelector("#metricGrid").innerHTML = [
    metricCard("组合净值", money(portfolio.total_value), `初始资金 ${money(portfolio.initial_capital || 150000)}`),
    metricCard("总盈亏", signedMoney(pnl), pctPoint(pnlPct), pnl >= 0 ? "good" : "bad"),
    metricCard("浮动盈亏", signedMoney(portfolio.unrealized_pnl), pctPoint(portfolio.unrealized_pnl_pct), asNumber(portfolio.unrealized_pnl) >= 0 ? "good" : "bad"),
    metricCard("现金", money(portfolio.cash), `现金占比 ${pctWeight(portfolio.cash_weight || 0)}`),
    metricCard("跑赢沪深300", pctPoint(comparison.excess_vs_csi300_pct || 0), `组合 ${pctPoint(comparison.portfolio_return_pct || 0)}`, asNumber(comparison.excess_vs_csi300_pct) >= 0 ? "good" : "bad"),
    metricCard("跑赢标普500", pctPoint(comparison.excess_vs_sp500_pct || 0), `标普 ${pctPoint(comparison.sp500_return_pct || 0)}`, asNumber(comparison.excess_vs_sp500_pct) >= 0 ? "good" : "bad"),
    metricCard("数据健康", `${health.score ?? "--"}分`, health.status_cn || "等待同步", (health.score || 0) >= 82 ? "good" : (health.score || 0) >= 60 ? "warn" : "bad"),
    metricCard("报告置信度", report.confidence ? `${report.confidence}%` : "--", report.as_of || "尚无报告"),
  ].join("");

  const pending = ((report && report.decisions) || []).filter((item) => item.status === "pending");
  document.querySelector("#todoList").innerHTML = pending.length
    ? pending.slice(0, 5).map(todoItem).join("")
    : emptyBlock("当前没有待确认的模拟交易。生成今日报告后，新的建议会出现在这里。");

  document.querySelector("#eventChainPreview").innerHTML = (state.events || []).length
    ? state.events.slice(0, 6).map(eventItem).join("")
    : emptyBlock("还没有事件数据，请先同步公开数据。");

  document.querySelector("#benchmarkSummary").innerHTML = [
    chip(`沪深300 ${pctPoint(comparison.csi300_return_pct || 0)}`, "neutral"),
    chip(`标普500 ${pctPoint(comparison.sp500_return_pct || 0)}`, "neutral"),
    chip(`回撤 ${plainPct(comparison.drawdown_pct || 0)}`, asNumber(comparison.drawdown_pct) > 10 ? "warn" : "neutral"),
  ].join("");
}

function renderPerformance() {
  const series = state.performance.length
    ? state.performance
    : [{ as_of: "Start", portfolio_value: 150000, csi300_equiv: 150000, sp500_equiv: 150000 }];
  drawLineChart("#performanceChart", series, [
    { key: "portfolio_value", color: "#16665a", label: "组合" },
    { key: "csi300_equiv", color: "#315f9f", label: "沪深300" },
    { key: "sp500_equiv", color: "#8b5f16", label: "标普500" },
  ], true);
}

function renderPositions() {
  const positions = (state.portfolio && state.portfolio.positions) || [];
  const list = document.querySelector("#positionsList");
  if (!positions.length) {
    list.innerHTML = emptyBlock("当前没有持仓，现金等待模拟交易确认。");
    return;
  }
  list.innerHTML = positions
    .map((position) => {
      const pnl = asNumber(position.unrealized_pnl);
      return `
        <div class="item">
          <div class="item-main">
            <strong>${escapeHtml(position.symbol)} ${escapeHtml(position.name_cn)}</strong>
            <span>${escapeHtml(assetClassLabel(position.asset_class))} · ${escapeHtml(position.currency)}</span>
          </div>
          <div class="item-stats">
            <span>市值 ${money(position.market_value)}</span>
            <span>成本 ${money(position.cost_value)}</span>
            <span class="${pnl >= 0 ? "pos" : "neg"}">盈亏 ${signedMoney(pnl)} / ${pctPoint(position.unrealized_pnl_pct)}</span>
            <span>权重 ${pctWeight(position.weight)}</span>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderReport() {
  const block = document.querySelector("#reportBlock");
  const report = state.report;
  if (!report) {
    block.innerHTML = emptyBlock("尚未生成报告。");
    return;
  }
  block.innerHTML = `
    <div class="report-head">
      <div>
        <strong>${escapeHtml(report.title_cn || "每日决策报告")}</strong>
        <span>${escapeHtml(report.title_en || "")}</span>
      </div>
      <div class="chip-row">
        ${chip(report.as_of || "--", "neutral")}
        ${chip(report.regime || "--", "neutral")}
        ${chip(`置信度 ${report.confidence || "--"}%`, "neutral")}
      </div>
    </div>
    <div class="narrative">
      <h3>核心判断</h3>
      <p>${escapeHtml(report.thesis_cn || "--")}</p>
      <h3>因果链</h3>
      <pre>${escapeHtml(report.chain_cn || "--")}</pre>
    </div>
  `;
}

function renderAiAdvice() {
  const block = document.querySelector("#aiAdviceBlock");
  const advice = state.aiAdvice;
  if (!advice) {
    block.innerHTML = emptyBlock("尚未生成 AI 当日建议。");
    return;
  }
  if (advice.status !== "ok") {
    block.innerHTML = emptyBlock(`AI 建议生成失败：${advice.error || advice.status}`);
    return;
  }
  block.innerHTML = `
    <div class="report-head">
      <div>
        <strong>AI 投资建议</strong>
        <span>${escapeHtml(advice.created_at || "")}</span>
      </div>
      <div class="chip-row">
        ${chip(advice.model || "model", "neutral")}
        ${chip(advice.as_of || "--", "neutral")}
      </div>
    </div>
    <pre class="advice-text">${escapeHtml(advice.advice_text || "")}</pre>
  `;
}

function renderExpertDebate() {
  const block = document.querySelector("#expertReportBlock");
  if (!block) return;
  const report = state.expertReport;
  if (!report) {
    block.innerHTML = emptyBlock("尚未生成专家辩论报告。");
    return;
  }
  const statusTone = report.status === "ok" ? "good" : report.status === "missing_key" ? "warn" : "bad";
  const title = report.status === "ok" ? "专家委员会最终报告" : "专家委员会报告（含兜底输出）";
  block.innerHTML = `
    <div class="report-head">
      <div>
        <strong>${title}</strong>
        <span>${escapeHtml(report.created_at || "")}</span>
      </div>
      <div class="chip-row">
        ${chip(report.as_of || "--", "neutral")}
        ${chip(report.model || "model", "neutral")}
        ${chip(report.status || "--", statusTone)}
      </div>
    </div>
    ${report.error ? `<div class="empty warn">生成提示：${escapeHtml(report.error)}</div>` : ""}
    <pre class="advice-text">${escapeHtml(report.final_report_md || "")}</pre>
  `;
}

function renderDecisions() {
  const wrap = document.querySelector("#decisionsTable");
  const decisions = (state.report && state.report.decisions) || [];
  if (!decisions.length) {
    wrap.innerHTML = emptyBlock("暂无模拟交易建议。");
    return;
  }
  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>动作</th>
          <th>标的</th>
          <th>仓位</th>
          <th>金额</th>
          <th>价格</th>
          <th>止损 / 止盈</th>
          <th>周期</th>
          <th>置信度</th>
          <th>状态</th>
          <th>人工确认</th>
        </tr>
      </thead>
      <tbody>${decisions.map(decisionRow).join("")}</tbody>
    </table>
  `;
  wrap.querySelectorAll("[data-confirm]").forEach((button) => {
    button.addEventListener("click", () => confirmDecision(button.dataset.confirm));
  });
  wrap.querySelectorAll("[data-reject]").forEach((button) => {
    button.addEventListener("click", () => rejectDecision(button.dataset.reject));
  });
}

function decisionRow(decision) {
  const actionClass = decision.action === "BUY" ? "buy" : decision.action === "SELL" ? "sell" : "hold";
  const controls =
    decision.status === "pending"
      ? `<div class="button-row tight">
          <button class="mini-btn" data-confirm="${escapeHtml(decision.id)}" type="button">确认</button>
          <button class="mini-btn danger" data-reject="${escapeHtml(decision.id)}" type="button">拒绝</button>
        </div>`
      : escapeHtml(decision.status);
  return `
    <tr>
      <td><span class="badge ${actionClass}">${escapeHtml(decision.action_cn)} ${escapeHtml(decision.action)}</span></td>
      <td><strong>${escapeHtml(decision.symbol)}</strong><br><span class="muted">${escapeHtml(decision.name_cn)} / ${escapeHtml(decision.name_en)}</span></td>
      <td>目标 ${pctWeight(decision.target_weight)}<br><span class="muted">当前 ${pctWeight(decision.current_weight)}</span></td>
      <td>${money(decision.amount_cny)}</td>
      <td>${fmtNum.format(asNumber(decision.price))}</td>
      <td>${fmtNum.format(asNumber(decision.stop_loss))} / ${fmtNum.format(asNumber(decision.take_profit))}</td>
      <td>${asNumber(decision.holding_days)} 天</td>
      <td>${asNumber(decision.confidence)}%</td>
      <td>${escapeHtml(decision.status)}</td>
      <td>${controls}</td>
    </tr>
  `;
}

function renderStocks() {
  const summary = state.stocks.summary || {};
  document.querySelector("#stockHeadline").textContent = `${summary.count || 0} 只个股，A 股 ${summary.a_share_count || 0}，港股 ${summary.hk_count || 0}`;
  document.querySelector("#stockSummary").innerHTML = [
    metricCard("平均涨跌", pctPoint(summary.avg_day_change_pct || 0), "个股池当日表现", asNumber(summary.avg_day_change_pct) >= 0 ? "good" : "bad"),
    metricCard("上涨个股", summary.positive_count || 0, "Positive names", "good"),
    metricCard("下跌个股", summary.negative_count || 0, "Negative names", asNumber(summary.negative_count) ? "bad" : "neutral"),
    metricCard("覆盖市场", "A / HK", "中国大陆与香港"),
  ].join("");

  renderStocksTable();
  renderStockDetail();
}

function renderUniverse() {
  const summary = state.universeSummary || {};
  const byMarket = Object.fromEntries((summary.by_market || []).map((item) => [item.market, item.count]));
  document.querySelector("#universeSummary").innerHTML = [
    metricCard("全市场标的", largeNumber(summary.total || 0), "A 股、港股、基金目录"),
    metricCard("中国大陆", largeNumber(byMarket.CN || 0), "A 股与场内基金"),
    metricCard("香港", largeNumber(byMarket.HK || 0), "港股市场"),
    metricCard("更新时间", summary.latest && summary.latest.updated_at ? formatTime(summary.latest.updated_at) : "--", "Eastmoney public quote"),
  ].join("");

  const wrap = document.querySelector("#universeTable");
  if (!state.universeRows.length) {
    wrap.innerHTML = emptyBlock("全市场目录为空。请点击“同步全市场目录”。");
  } else {
    wrap.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>市场 / 品类</th>
            <th>行业 / 板块</th>
            <th>价格</th>
            <th>涨跌幅</th>
            <th>成交额</th>
            <th>市值</th>
            <th>估值</th>
          </tr>
        </thead>
        <tbody>${state.universeRows.map(universeRow).join("")}</tbody>
      </table>
    `;
  }

  const start = state.universeTotal ? state.universeOffset + 1 : 0;
  const end = Math.min(state.universeOffset + state.universeLimit, state.universeTotal);
  setText("#universePageInfo", `${start}-${end} / ${largeNumber(state.universeTotal)}`);
  document.querySelector("#universePrev").disabled = state.universeOffset <= 0;
  document.querySelector("#universeNext").disabled = state.universeOffset + state.universeLimit >= state.universeTotal;
}

function universeRow(item) {
  const change = asNumber(item.day_change_pct);
  return `
    <tr>
      <td><strong>${escapeHtml(item.symbol)}</strong><br><span class="muted">${escapeHtml(item.code)}</span></td>
      <td>${escapeHtml(item.name_cn)}</td>
      <td>${escapeHtml(item.market)}<br><span class="muted">${escapeHtml(assetClassLabel(item.asset_class))} / ${escapeHtml(item.product_type)}</span></td>
      <td>${escapeHtml(item.sector)}<br><span class="muted">${escapeHtml(item.board)}</span></td>
      <td>${item.price === null ? "--" : fmtNum.format(asNumber(item.price))}</td>
      <td class="${change >= 0 ? "pos" : "neg"}">${pctPoint(change)}</td>
      <td>${largeMoney(item.turnover)}</td>
      <td>${largeMoney(item.market_cap)}</td>
      <td>PE ${formatOptional(item.pe_ttm)}<br><span class="muted">PB ${formatOptional(item.pb)}</span></td>
    </tr>
  `;
}

function renderStocksTable() {
  const wrap = document.querySelector("#stocksTable");
  const query = state.stockQuery.trim().toLowerCase();
  const stocks = (state.stocks.stocks || []).filter((stock) => {
    if (!query) return true;
    return [stock.symbol, stock.name_cn, stock.name_en, stock.market, stock.bucket]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
  if (!stocks.length) {
    wrap.innerHTML = emptyBlock("没有匹配的个股。");
    return;
  }
  wrap.innerHTML = `
    <table class="stock-table">
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>市场</th>
          <th>价格</th>
          <th>当日</th>
          <th>质量/动量</th>
          <th>风险标签</th>
          <th>详情</th>
        </tr>
      </thead>
      <tbody>
        ${stocks.map(stockRow).join("")}
      </tbody>
    </table>
  `;
  wrap.querySelectorAll("[data-stock]").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await loadStockDetail(button.dataset.stock);
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

function stockRow(stock) {
  const selected = stock.symbol === state.selectedStockSymbol ? "selected" : "";
  const day = asNumber(stock.day_change_pct);
  return `
    <tr class="${selected}">
      <td><strong>${escapeHtml(stock.symbol)}</strong></td>
      <td>${escapeHtml(stock.name_cn)}<br><span class="muted">${escapeHtml(stock.name_en)}</span></td>
      <td>${escapeHtml(stock.market)} · ${escapeHtml(stock.currency)}</td>
      <td>${fmtNum.format(asNumber(stock.price))}</td>
      <td class="${day >= 0 ? "pos" : "neg"}">${pctPoint(day)}</td>
      <td>${asNumber(stock.quality_score)} / ${asNumber(stock.momentum_score)}</td>
      <td>${escapeHtml(stock.risk_bucket)}<br><span class="muted">${escapeHtml(stock.bucket)}</span></td>
      <td><button class="mini-btn" data-stock="${escapeHtml(stock.symbol)}" type="button">查看</button></td>
    </tr>
  `;
}

function renderStockDetail() {
  const block = document.querySelector("#stockDetail");
  const detail = state.stockDetail;
  if (!detail || !detail.stock) {
    block.innerHTML = emptyBlock("请选择一只股票。");
    drawLineChart("#stockChart", [], [], false);
    return;
  }
  const stock = detail.stock;
  const day = asNumber(stock.day_change_pct);
  block.innerHTML = `
    <div class="detail-title">
      <div>
        <strong>${escapeHtml(stock.symbol)} ${escapeHtml(stock.name_cn)}</strong>
        <span>${escapeHtml(stock.name_en)} · ${escapeHtml(stock.market)} · ${escapeHtml(stock.currency)}</span>
      </div>
      <span class="score">${escapeHtml(String(detail.score))}</span>
    </div>
    <div class="detail-metrics">
      <div><span>最新价</span><strong>${fmtNum.format(asNumber(stock.price))}</strong></div>
      <div><span>当日</span><strong class="${day >= 0 ? "pos" : "neg"}">${pctPoint(day)}</strong></div>
      <div><span>历史区间</span><strong>${pctPoint(detail.history_change_pct || 0)}</strong></div>
      <div><span>状态</span><strong>${escapeHtml(detail.view)}</strong></div>
    </div>
    <div class="risk-notes">
      ${(detail.risk_flags || []).map((flag) => `<span>${escapeHtml(flag)}</span>`).join("") || "<span>暂无显著风险标签</span>"}
    </div>
    <div class="mini-section">
      <strong>相关事件</strong>
      <div class="item-list small">
        ${(detail.related_events || []).slice(0, 4).map(eventItem).join("") || emptyBlock("暂无直接匹配事件。")}
      </div>
    </div>
  `;
  drawLineChart("#stockChart", detail.history || [], [
    { key: "price", color: "#16665a", label: "价格" },
  ], false);
}

function renderDataHealth() {
  const health = state.dataHealth || {};
  setText("#dataHealthTitle", `${health.status_cn || "未知"} · 健康评分 ${health.score ?? "--"} 分`);
  document.querySelector("#dataHealthGrid").innerHTML = [
    metricCard("健康评分", `${health.score ?? "--"}分`, health.status_cn || "等待同步", (health.score || 0) >= 82 ? "good" : (health.score || 0) >= 60 ? "warn" : "bad"),
    metricCard("行情日期", (health.market_data && health.market_data.latest_as_of) || "--", ageText(health.quote_age_days)),
    metricCard("行情记录", health.market_data ? health.market_data.records || 0 : 0, `${health.market_data ? health.market_data.symbols || 0 : 0} 个标的`),
    metricCard("公共原文", health.documents_count || 0, ageText(health.document_age_days)),
    metricCard("全市场目录", health.market_universe ? health.market_universe.total || 0 : 0, ageText(health.universe_age_days)),
  ].join("");

  document.querySelector("#coverageGrid").innerHTML = (health.coverage || [])
    .map(
      (item) => `
      <div class="coverage-item ${item.status === "ok" ? "" : "missing"}">
        <span>${escapeHtml(item.label)}</span>
        <strong>${asNumber(item.count)}</strong>
        <small>${item.latest_at ? escapeHtml(formatTime(item.latest_at)) : "暂无"}</small>
      </div>
    `,
    )
    .join("");

  renderSourceRuns();
  renderRawDocuments();
}

function renderSourceRuns() {
  const wrap = document.querySelector("#sourceRuns");
  const runs = (state.dataHealth && state.dataHealth.latest_runs) || state.sourceRuns || [];
  if (!runs.length) {
    wrap.innerHTML = emptyBlock("尚未同步公开数据。");
    return;
  }
  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>数据源</th>
          <th>开始时间</th>
          <th>状态</th>
          <th>记录</th>
          <th>错误</th>
        </tr>
      </thead>
      <tbody>
        ${runs
          .map(
            (run) => `
          <tr>
            <td><strong>${escapeHtml(run.source)}</strong></td>
            <td>${escapeHtml(formatTime(run.started_at))}</td>
            <td>${run.status === "ok" ? chip("正常", "good") : chip(run.status || "异常", "bad")}</td>
            <td>${asNumber(run.records)}</td>
            <td>${escapeHtml(run.error || "")}</td>
          </tr>
        `,
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderRawDocuments() {
  const list = document.querySelector("#rawDocuments");
  const docs = state.rawDocuments || [];
  if (!docs.length) {
    list.innerHTML = emptyBlock("暂无公共信息原文。");
    return;
  }
  list.innerHTML = docs.slice(0, 16).map(documentItem).join("");
}

function renderEvents() {
  const list = document.querySelector("#eventsList");
  if (!state.events.length) {
    list.innerHTML = emptyBlock("暂无自动事件，请先同步公开数据。");
    return;
  }
  list.innerHTML = state.events.slice(0, 60).map(eventItem).join("");
}

function renderAssets() {
  const exposures = (state.portfolio && state.portfolio.exposures) || {};
  const bars = Object.entries(exposures).sort((a, b) => b[1] - a[1]);
  document.querySelector("#allocationBars").innerHTML = bars.length
    ? bars
        .map(
          ([bucket, value]) => `
          <div class="bar-row">
            <div><strong>${escapeHtml(bucketLabel(bucket))}</strong><span>${pctWeight(value)}</span></div>
            <div class="bar-track"><span style="width:${Math.min(100, asNumber(value) * 100)}%"></span></div>
          </div>
        `,
        )
        .join("")
    : emptyBlock("暂无持仓暴露。");

  const wrap = document.querySelector("#assetsTable");
  wrap.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>代码</th>
          <th>名称</th>
          <th>类别</th>
          <th>市场</th>
          <th>价格</th>
          <th>当日</th>
          <th>年初至今</th>
          <th>波动</th>
          <th>状态</th>
        </tr>
      </thead>
      <tbody>
        ${state.assets.map(assetRow).join("")}
      </tbody>
    </table>
  `;
}

function assetRow(asset) {
  const day = asNumber(asset.day_change_pct);
  return `
    <tr>
      <td><strong>${escapeHtml(asset.symbol)}</strong></td>
      <td>${escapeHtml(asset.name_cn)}<br><span class="muted">${escapeHtml(asset.name_en)}</span></td>
      <td>${escapeHtml(assetClassLabel(asset.asset_class))}<br><span class="muted">${escapeHtml(asset.product_type)}</span></td>
      <td>${escapeHtml(asset.market)} · ${escapeHtml(asset.currency)}</td>
      <td>${fmtNum.format(asNumber(asset.price))}</td>
      <td class="${day >= 0 ? "pos" : "neg"}">${pctPoint(day)}</td>
      <td>${pctPoint(asset.ytd_return_pct)}</td>
      <td>${plainPct(asset.volatility_20d)}</td>
      <td>${asset.tradable ? "可模拟交易" : "仅观察"}</td>
    </tr>
  `;
}

function renderRisk() {
  const policy = (state.config && state.config.risk_policy) || {};
  const items = [
    ["最大回撤", `${policy.max_drawdown_pct || 20}%`],
    ["单一资产上限", pctWeight(policy.single_asset_max_weight || 0)],
    ["单只股票上限", pctWeight(policy.single_stock_max_weight || 0)],
    ["黄金上限", pctWeight(policy.gold_max_weight || 0)],
    ["原油上限", pctWeight(policy.oil_max_weight || 0)],
    ["最低现金", pctWeight(policy.cash_min_weight || 0)],
    ["做空", policy.short_selling_allowed ? "允许" : "禁止"],
    ["杠杆", policy.leverage_allowed ? "允许" : "禁止"],
    ["真实交易", policy.real_trading_enabled ? "开启" : "关闭"],
  ];
  document.querySelector("#riskPolicy").innerHTML = items
    .map(
      ([label, value]) => `
      <div class="coverage-item">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>
    `,
    )
    .join("");
}

function todoItem(decision) {
  return `
    <div class="item action-item">
      <div class="item-main">
        <strong>${escapeHtml(decision.action_cn)} ${escapeHtml(decision.symbol)}</strong>
        <span>${escapeHtml(decision.name_cn)} · ${money(decision.amount_cny)} · 目标 ${pctWeight(decision.target_weight)}</span>
      </div>
      <div class="item-stats">
        <span>价格 ${fmtNum.format(asNumber(decision.price))}</span>
        <span>止损 ${fmtNum.format(asNumber(decision.stop_loss))}</span>
        <span>止盈 ${fmtNum.format(asNumber(decision.take_profit))}</span>
      </div>
    </div>
  `;
}

function eventItem(event) {
  const sentimentClass = asNumber(event.sentiment) > 0 ? "good" : asNumber(event.sentiment) < 0 ? "bad" : "neutral";
  return `
    <div class="item">
      <div class="item-main">
        <strong>${escapeHtml(event.title_cn || event.title_en || "事件")}</strong>
        <span>${escapeHtml(event.title_en || "")}</span>
      </div>
      <div class="item-stats">
        ${chip(categoryLabel(event.category), "neutral")}
        ${chip(`情绪 ${asNumber(event.sentiment)}`, sentimentClass)}
        <span>${escapeHtml(event.region || "")}</span>
        <span>${escapeHtml(event.source_type || event.source || "")}</span>
        <span>强度 ${asNumber(event.severity)}</span>
        <span>置信度 ${asNumber(event.confidence)}%</span>
      </div>
      ${event.link ? `<a href="${escapeHtml(event.link)}" target="_blank" rel="noreferrer">查看来源</a>` : ""}
    </div>
  `;
}

function documentItem(doc) {
  return `
    <div class="item">
      <div class="item-main">
        <strong>${escapeHtml(doc.title_cn || doc.title_en || "公共信息")}</strong>
        <span>${escapeHtml(doc.source || "")} · ${escapeHtml(formatTime(doc.published_at || doc.fetched_at))}</span>
      </div>
      <div class="item-stats">
        ${chip(categoryLabel(doc.category), "neutral")}
        <span>${escapeHtml(doc.region || "")}</span>
        <span>强度 ${asNumber(doc.severity)}</span>
        <span>置信度 ${asNumber(doc.confidence)}%</span>
      </div>
      ${doc.source_url ? `<a href="${escapeHtml(doc.source_url)}" target="_blank" rel="noreferrer">查看来源</a>` : ""}
    </div>
  `;
}

function metricCard(label, value, subtext, tone = "neutral") {
  return `
    <article class="metric ${tone}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
      <small>${escapeHtml(String(subtext || ""))}</small>
    </article>
  `;
}

function chip(text, tone = "neutral") {
  return `<span class="chip ${tone}">${escapeHtml(text)}</span>`;
}

function emptyBlock(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

function drawLineChart(selector, rows, lines, isMoneyChart) {
  const canvas = document.querySelector(selector);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);

  if (!rows.length || !lines.length) {
    ctx.fillStyle = "#6b7280";
    ctx.font = "14px Microsoft YaHei UI, Segoe UI, Arial";
    ctx.fillText("暂无可绘制数据", 18, 34);
    return;
  }

  const values = rows.flatMap((row) => lines.map((line) => asNumber(row[line.key]))).filter((value) => value > 0);
  if (!values.length) {
    ctx.fillStyle = "#6b7280";
    ctx.font = "14px Microsoft YaHei UI, Segoe UI, Arial";
    ctx.fillText("暂无可绘制数据", 18, 34);
    return;
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const min = minValue === maxValue ? minValue * 0.98 : minValue * 0.995;
  const max = minValue === maxValue ? maxValue * 1.02 : maxValue * 1.005;
  const left = 70;
  const right = width - 24;
  const top = 24;
  const bottom = height - 50;

  ctx.strokeStyle = "#d9dee7";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = top + ((bottom - top) / 3) * i;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();
  }

  lines.forEach((line) => {
    ctx.strokeStyle = line.color;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    rows.forEach((row, index) => {
      const x = left + ((right - left) * index) / Math.max(1, rows.length - 1);
      const y = bottom - ((asNumber(row[line.key]) - min) / Math.max(1, max - min)) * (bottom - top);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });

  ctx.font = "12px Microsoft YaHei UI, Segoe UI, Arial";
  ctx.fillStyle = "#6b7280";
  ctx.fillText(isMoneyChart ? money(max) : fmtNum.format(max), 8, top + 4);
  ctx.fillText(isMoneyChart ? money(min) : fmtNum.format(min), 8, bottom + 4);
  lines.forEach((line, index) => {
    const x = left + index * 112;
    ctx.fillStyle = line.color;
    ctx.fillRect(x, height - 26, 18, 3);
    ctx.fillStyle = "#1f2937";
    ctx.fillText(line.label, x + 26, height - 21);
  });
}

async function runDaily() {
  try {
    showToast("正在同步数据并生成报告");
    const data = await api("/api/daily/run", { method: "POST", body: "{}" });
    state.report = data.report;
    await loadAll();
    showToast("今日报告已生成");
  } catch (error) {
    showToast(error.message);
  }
}

async function syncData() {
  try {
    showToast("正在同步公开数据");
    await api("/api/data/sync", { method: "POST", body: "{}" });
    await loadAll();
    showToast("公开数据已同步");
  } catch (error) {
    showToast(error.message);
  }
}

async function syncUniverse() {
  try {
    showToast("正在同步全市场目录，可能需要几十秒");
    await api("/api/universe/sync", { method: "POST", body: "{}" });
    const [summary, page, health] = await Promise.all([
      api("/api/universe/summary"),
      fetchUniversePage(false),
      api("/api/data/health"),
    ]);
    state.universeSummary = summary.summary;
    state.universeRows = page.rows || [];
    state.universeTotal = page.total || 0;
    state.universeOffset = page.offset || 0;
    state.universeLimit = page.limit || state.universeLimit;
    state.dataHealth = health.health;
    renderUniverse();
    renderDataHealth();
    showToast("全市场目录已同步");
  } catch (error) {
    showToast(error.message);
  }
}

async function generateAiAdvice() {
  try {
    showToast("正在生成 AI 当日建议");
    const data = await api("/api/ai/advice", { method: "POST", body: JSON.stringify({ sync: false }) });
    state.aiAdvice = data.advice;
    renderAiAdvice();
    showToast(data.advice.status === "ok" ? "AI 建议已生成" : "AI 建议生成失败");
  } catch (error) {
    showToast(error.message);
  }
}

async function generateExpertReport() {
  try {
    showToast("正在生成专家辩论报告，可能需要一两分钟");
    const data = await api("/api/expert-debate/run", { method: "POST", body: JSON.stringify({ sync: false }) });
    state.expertReport = data.report;
    renderExpertDebate();
    showToast(data.report.status === "ok" ? "专家辩论报告已生成" : "专家辩论报告已生成兜底版本");
  } catch (error) {
    showToast(error.message);
  }
}

async function confirmDecision(id) {
  try {
    const result = await api(`/api/decisions/${id}/confirm`, { method: "POST", body: "{}" });
    await loadAll();
    showToast(`已确认：${result.action || "HOLD"}`);
  } catch (error) {
    showToast(error.message);
  }
}

async function rejectDecision(id) {
  try {
    await api(`/api/decisions/${id}/reject`, { method: "POST", body: "{}" });
    await loadAll();
    showToast("已拒绝");
  } catch (error) {
    showToast(error.message);
  }
}

function setupEvents() {
  document.querySelector("#runDailyBtn").addEventListener("click", runDaily);
  document.querySelector("#syncDataBtn").addEventListener("click", syncData);
  document.querySelector("#syncUniverseBtn").addEventListener("click", syncUniverse);
  document.querySelector("#syncUniverseBtnInline")?.addEventListener("click", syncUniverse);
  document.querySelector("#syncDataBtnInline")?.addEventListener("click", syncData);
  document.querySelector("#aiAdviceBtn").addEventListener("click", generateAiAdvice);
  document.querySelector("#aiAdviceBtnTop").addEventListener("click", generateAiAdvice);
  document.querySelector("#expertReportBtn")?.addEventListener("click", generateExpertReport);
  document.querySelector("#expertReportBtnTop")?.addEventListener("click", generateExpertReport);
  document.querySelector("#refreshBtn").addEventListener("click", loadAll);
  document.querySelector("#pdfBtn").addEventListener("click", () => {
    if (state.report) window.open(`/api/reports/${state.report.id}/pdf`, "_blank");
  });
  document.querySelector("#excelBtn").addEventListener("click", () => {
    if (state.report) window.open(`/api/reports/${state.report.id}/excel`, "_blank");
  });
  document.querySelector("#expertPdfBtn")?.addEventListener("click", () => {
    if (state.expertReport) window.open("/api/expert-debate/latest/pdf", "_blank");
  });
  document.querySelector("#expertExcelBtn")?.addEventListener("click", () => {
    if (state.expertReport) window.open("/api/expert-debate/latest/excel", "_blank");
  });
  document.querySelector("#expertMarkdownBtn")?.addEventListener("click", () => {
    if (state.expertReport) window.open("/api/expert-debate/latest/markdown", "_blank");
  });
  document.querySelector("#stockSearch").addEventListener("input", (event) => {
    state.stockQuery = event.target.value;
    renderStocksTable();
  });
  document.querySelector("#universeSearch").addEventListener("input", debounce((event) => {
    state.universeFilters.search = event.target.value.trim();
    state.universeOffset = 0;
    fetchUniversePage().catch((error) => showToast(error.message));
  }, 350));
  document.querySelector("#universeMarket").addEventListener("change", (event) => {
    state.universeFilters.market = event.target.value;
    state.universeOffset = 0;
    fetchUniversePage().catch((error) => showToast(error.message));
  });
  document.querySelector("#universeClass").addEventListener("change", (event) => {
    state.universeFilters.asset_class = event.target.value;
    state.universeOffset = 0;
    fetchUniversePage().catch((error) => showToast(error.message));
  });
  document.querySelector("#universeSort").addEventListener("change", (event) => {
    state.universeFilters.sort = event.target.value;
    state.universeOffset = 0;
    fetchUniversePage().catch((error) => showToast(error.message));
  });
  document.querySelector("#universePrev").addEventListener("click", () => {
    state.universeOffset = Math.max(0, state.universeOffset - state.universeLimit);
    fetchUniversePage().catch((error) => showToast(error.message));
  });
  document.querySelector("#universeNext").addEventListener("click", () => {
    if (state.universeOffset + state.universeLimit < state.universeTotal) {
      state.universeOffset += state.universeLimit;
      fetchUniversePage().catch((error) => showToast(error.message));
    }
  });
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((node) => node.classList.remove("active"));
      document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`#${tab.dataset.tab}`).classList.add("active");
      if (tab.dataset.tab === "stocks") renderStockDetail();
    });
  });
}

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function setText(selector, value) {
  const node = document.querySelector(selector);
  if (node) node.textContent = value;
}

function debounce(fn, waitMs) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), waitMs);
  };
}

function formatTime(value) {
  if (!value) return "--";
  return String(value).replace("T", " ").slice(0, 19);
}

function ageText(days) {
  if (days === null || days === undefined) return "未检测到";
  if (days === 0) return "今日更新";
  return `${days} 天前`;
}

function categoryLabel(category) {
  const labels = {
    bond: "债券",
    future: "期货",
    fx: "外汇",
    stock: "股票",
    gold: "黄金",
    energy: "能源",
    technology: "科技",
    geopolitics: "地缘",
    macro: "宏观",
    market: "市场",
    policy: "政策",
    company: "公司",
  };
  return labels[category] || category || "事件";
}

function assetClassLabel(value) {
  const labels = {
    equity: "股票",
    fund: "基金",
    bond: "债券",
    fx: "外汇",
    future: "期货",
    forward: "远期",
    gold: "黄金",
    oil: "能源",
    money: "货币",
  };
  return labels[value] || value || "资产";
}

function bucketLabel(value) {
  const labels = {
    china_equity: "中国权益",
    hk_equity: "港股权益",
    global_equity: "全球权益",
    bond: "债券",
    money: "货币",
    gold: "黄金",
    oil: "能源",
    fx: "外汇",
  };
  return labels[value] || value || "其他";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

setupEvents();
loadAll().catch((error) => showToast(error.message));
