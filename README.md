# SimVest 2.0 模拟投资驾驶舱

SimVest 是一个本地运行的模拟投资系统，用于把公开行情、宏观信息、地缘事件、科技与公司动态转化为每日市场主线、组合估值和可人工确认的模拟交易建议。

当前版本仍然是 **simulation only**：不会连接真实券商，不会发送真实订单。

## 当前能力

- 本地网页驾驶舱：`http://127.0.0.1:8000`
- 多资产池：股票、基金、债券、外汇、期货模拟、远期模拟、黄金、能源
- A 股 / 港股个股工作台：个股列表、详情、价格历史、风险标签、相关事件
- 全市场目录：批量覆盖 A 股、港股、场内基金 / ETF，支持搜索、分页、市场与品类筛选
- 持仓每日估值：组合净值、总盈亏、浮动盈亏、现金比例、资产暴露
- 双基准比较：沪深300、标普500
- 数据健康中心：行情新鲜度、事件覆盖、来源同步状态、公共信息原文
- 自动事件流：债券、期货、外汇、股票、黄金、能源、科技、地缘、宏观
- 每日决策报告：市场主线、因果链、风险档位、具体模拟建议
- AI 当日建议：基于当前持仓、同步数据、事件流、风险约束生成
- 专家委员会报告：公开数据、组合估值、事件因果链三位专家分别分析并辩论，由投委会主席汇总成中英双语商业报告
- 人工确认闭环：只有确认后才记录模拟交易
- PDF / Excel 报告导出

## 启动

```powershell
python -m simvest.server --host 127.0.0.1 --port 8000
```

也可以使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_server.ps1
```

然后打开：

```text
http://127.0.0.1:8000
```

## 日常使用顺序

1. 点击“同步公开数据”
2. 定期点击“同步全市场目录”，更新 A 股、港股和 ETF 的大范围标的库
3. 查看“数据健康”，确认行情、事件和全市场目录是否更新
4. 查看“驾驶舱”，确认组合盈亏、主线、风险状态
5. 点击“生成今日报告”
6. 点击“生成 AI 建议”
7. 点击“生成专家辩论报告”，下载 PDF、Excel 或 Markdown 版本
8. 在“决策”页人工确认或拒绝每一条模拟交易建议
9. 在“股票工作台”查看核心个股和全市场目录

## AI 密钥

复制 `data/secrets.example.json` 为 `data/secrets.json`，填入自己的 OpenAI-compatible API Key。
`data/secrets.json` 已加入 `.gitignore`，不要上传到 GitHub。

## 重要边界

- 不保证一年收益率一定高于指数
- 系统会把跑赢沪深300和标普500作为评估目标
- 建议只用于模拟投资和研究，不构成真实投资建议
- 不做空、不使用杠杆、不自动下真实订单
- 任何交易建议都必须人工确认后才会记录为模拟交易
- 免费公开数据源可能限流、延迟或变更格式，系统会记录失败原因
- “核心投资池”用于组合决策和交易建议；“全市场目录”用于覆盖、检索和未来信息挂载，不代表所有标的都会自动进入组合建议
- AI 建议不会把上万只标的全部塞进上下文，而是读取全市场概要、核心池、成交额前列和异常涨跌标的，避免上下文过载

## 常用 API

- `GET /api/dashboard`：驾驶舱聚合数据
- `GET /api/data/health`：数据健康中心
- `POST /api/data/sync`：同步公开数据
- `POST /api/universe/sync`：同步全市场目录
- `GET /api/universe/summary`：全市场目录概要
- `GET /api/universe`：全市场目录分页查询
- `GET /api/universe/{symbol}`：全市场标的详情
- `GET /api/stocks`：A 股 / 港股个股列表
- `GET /api/stocks/{symbol}`：个股详情
- `GET /api/portfolio`：组合估值
- `GET /api/events`：事件流
- `POST /api/daily/run`：同步并生成今日报告
- `GET /api/reports/latest`：最新报告
- `POST /api/ai/advice`：生成 AI 当日建议
- `GET /api/expert-debate/prompts`：查看专家角色和投委会主席提示词
- `POST /api/expert-debate/run`：生成专家辩论报告
- `GET /api/expert-debate/latest`：读取最新专家辩论报告
- `GET /api/expert-debate/latest/pdf`：下载最新专家报告 PDF
- `GET /api/expert-debate/latest/excel`：下载最新专家报告 Excel
- `GET /api/expert-debate/latest/markdown`：下载最新专家报告 Markdown
- `POST /api/decisions/{id}/confirm`：确认模拟交易
- `POST /api/decisions/{id}/reject`：拒绝模拟交易

## 打包和发布

建议发布到 GitHub 时包含：

- `simvest/`
- `static/`
- `scripts/`
- `docs/`
- `data/sources.json`
- `data/secrets.example.json`
- `README.md`
- `requirements.txt`
- `.gitignore`

不要包含：

- `data/secrets.json`
- `data/*.sqlite3*`
- `server.log`
- `output/` 内的私人报告，除非你明确想发布样例

## 后续建议

下一阶段建议优先补三类能力：

1. 回测与复盘：胜率、盈亏比、回撤、策略失效监控
2. 更深的个股数据：公告、财务摘要、行业对比、估值分位
3. 定时任务：每天自动同步、自动生成报告、提醒人工确认
