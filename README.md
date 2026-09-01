# AiAgentForTrading

基于 **Alpaca API**、**LangGraph 多智能体协同状态图** 与 **大语言模型（LLM）** 的全流程量化交易决策、正股与垂直价差期权双轨执行、动态移动止盈止损及风险治理系统。

系统集成了 **实时宏观体制检测（Market Regime）**、**5 大策略研究智能体并行辩论与共识**、**正股/垂直价差期权混合资产提案生成（Hybrid Memo / Bull Call Spread）**、**独立 Critic 审查**、**CLI 人机协同决策治理（Human-in-the-Loop）**、**确定性硬风控拦截（RiskGuard）**、**持仓与期权临期守护引擎（Sentinel）** 以及 **股票+期权多品种事件驱动回测引擎（HybridStrategyBacktester）**。

---

## 🌟 核心特性

- **多智能体并行辩论与共识机制 (LangGraph StateGraph)**：
  - **Momentum Agent (动量策略)**：基于均线突破 (SMA)、RSI 与成交量异动捕捉趋势。
  - **Macro Agent (宏观基本面)**：结合 VIX 恐慌指数与 FRED 高收益信用利差评估市场风险偏好。
  - **StatArb Agent (统计套利)**：监控与 SPY 标杆的滚动相关系数与价差 Z-Score 均值回归。
  - **Contrarian Agent (逆向投资)**：利用市场恐慌指数与超卖程度逆势寻找非对称博弈机会。
  - **Exotic Agent (衍生品与事件驱动)**：分析期权看涨/看跌比率 (PCR)、异常期权活动与财报窗口期。
- **动态宏观体制裁定 (Regime Engine)**：
  - 自动识别 `Bull_Trend` (多头趋势)、`High_Vol_Bear` (高波熊市)、`Panic_Crisis` (恐慌危机) 与 `Neutral_Range` (震荡模式)。
  - 依据宏观模式动态调配 5 大策略智能体的权重矩阵。
- **正股 + 牛市看涨期权价差双轨资产决策 (Hybrid Investment Memo & Bull Call Spread)**：
  - **正股配置（Common Stock）**：趋势明显或低波动环境下稳健配置。
  - **牛市看涨垂直价差策略（Bull Call Spread）**：自动构建买入低行权价 Call (Long Leg) + 卖出高行权价 Call (Short Leg)，压降权利金支出并规避波动率暴跌风险。
  - **智能资产路由**：支持 `AUTO`（智能权衡）、`EQUITY`（仅正股）与 `OPTION`（仅期权）。
  - **Black-Scholes 期权二元定价与希腊字母计算**：精确计算组合 Net Delta、Net Gamma、Net Theta 与 Net Vega。
- **双重风控防御与移动止盈保本体系**：
  - **Critic 独立合规审查**：校验标的池白名单、期权 DTE 周期约束 (14 ~ 60天)、权利金成本上限 (<=2.0%) 以及 7 天二元财报事件一票否决。
  - **确定性 Python 硬风控 (RiskGuard)**：不依赖 LLM，代码级拦截正股单仓上限 (10%)、期权单笔权利金 (2.0%)、期权总敞口 (10.0%)、板块集中度 (30%) 及日内浮亏熔断 (5%)。
  - **阶梯保本 / 移动止盈 (Trailing Stop & Break-Even Protection)**：期权浮盈达 +25% 时止损线上移至成本价（BE 0%），浮盈达 +40% 时止损线上移锁定 +15% 利润。
- **持仓与期权临期守护引擎 (Sentinel)**：
  - **Sentinel 临期平仓 (DTE Guard)**：期权持仓 `DTE <= 3` 天时自动市价平仓锁定剩余价差价值，彻底规避行权交割与末日流动性风险。
  - **正股锚定止损**：正股跌破进场价支撑线 (-4%) 联动触发期权止损平仓。
  - **孤儿持仓对冲**：定期巡检正股持仓，自动补齐缺失的止盈止损挂单。
- **混合策略历史回测引擎 (HybridStrategyBacktester)**：
  - 支持股票 + 期权价差在真实历史行情（Yahoo Finance / yfinance 真实日 K 与 VIX）下的事件驱动回测。
  - 自动输出 **数据质量检验报告（Data Quality Report）**、**整体资产净值曲线（CAGR / MaxDD / Sharpe / Sortino）**、**分品种独立收益拆解（Stock vs Option）** 及 **出场原因归因明细**。
- **人机协同终端治理 (HitL CLI Terminal)**：
  - 丰富的富文本交互看板（`rich`），支持连续分析决策（REPL 循环）。
  - 支持分资产类型参数微调（正股股数 vs 期权张数与止盈止损）。
  - 一键执行审批 (`A`)、驳回 (`R`)、微调参数 (`E`) 或跳过 (`S`)，审批通过后自动下发 Bracket OCO 或期权限价单。
- **不可变审计追踪 (Audit Trail)**：
  - 所有订单下发、参数变更与持仓自愈记录均写入不可篡改的 `logs/audit_trail.jsonl`。

---

## 🏗️ 系统架构流程

```mermaid
flowchart TD
    A[启动主交互终端 main.py] --> B[同步 Alpaca 账户 & 实时宏观指标 VIX / HY Spread]
    B --> C[Regime Engine 裁定宏观体制并分配策略权重]
    C --> D[拉取标的池实时行情快照 config/sp500_universe.json]
    D --> E[操作员交互选择标的代码与交易倾向 AUTO/EQUITY/OPTION]
    E --> F[LangGraph 调度 5 大策略 Agent 并行辩论]
    F --> G{加权共识得分 >= 0.70 ?}
    G -- 否 --> H[提示未达门槛，返回主菜单]
    G -- 是 --> I[生成 HybridInvestmentMemo 并提交 Critic Agent 独立审查]
    I -- 拒绝 --> J[输出违规原因，终止流程]
    I -- 通过 --> K[CLI 高亮渲染正股/期权投资决策备忘录 Panel]
    K --> L{HitL 人机审批流}
    L -- R 驳回 / S 跳过 --> M[记录审计，返回主菜单]
    L -- E 微调 --> N[微调正股股数/期权张数与止盈止损]
    L -- A 通过 / 完成微调 --> O[RiskGuard 确定性硬风控拦截校验]
    O -- 拦截违规 --> P[阻断下单，输出风控警报]
    O -- 校验通过 --> Q[向 Alpaca API 下发 Bracket OCO 正股单或期权限价单]
    Q --> R[写入不可变审计日志 logs/audit_trail.jsonl]
    R --> S[按 Enter 键循环进入下一轮决策]
```

---

## 📁 项目目录结构

```text
AiAgentForTrading/
├── backtest/                          # 历史回测系统
│   ├── __init__.py                    # 回测模块导出
│   ├── backtest_engine.py             # 经典事件驱动回测引擎
│   ├── config.py                      # 回测参数配置与混合持仓数据模型
│   └── hybrid_backtester.py           # 股票+期权价差混合回测核心引擎 (移动止盈/阶梯保本/临期平仓)
├── cli/
│   └── terminal_ui.py                 # 终端富文本渲染面板 (Rich Hybrid Memo Panel)
├── config/
│   ├── settings.yaml                  # 全局系统配置 (Alpaca / Featherless / 风控阈值)
│   ├── investment_memo.yaml           # Critic 独立审查合规规则 (正股 + 期权)
│   └── sp500_universe.json            # 标普 500 核心标的池白名单 (40+ 核心蓝筹覆盖 7 大行业)
├── core/
│   ├── agents/                        # 5 大策略研究 Agent 与 Critic Agent
│   │   ├── base_agent.py              # 智能体基类 (抽象评估接口与 LLM 封装)
│   │   ├── momentum_agent.py          # 动量趋势智能体
│   │   ├── macro_agent.py             # 宏观基本面智能体
│   │   ├── statarb_agent.py           # 统计套利智能体
│   │   ├── contrarian_agent.py        # 逆向反转智能体
│   │   ├── exotic_agent.py            # 衍生品与事件驱动智能体
│   │   └── critic_agent.py            # 独立审查智能体 (一票否决权)
│   ├── alpaca_client.py               # Alpaca API 统一网关客户端 (正股 + 期权交易与行情)
│   ├── consensus_engine.py            # 基于 LangGraph 的多智能体共识与混合资产决策引擎
│   ├── options_engine.py              # 期权牛市看涨价差 (Bull Call Spread) 定价与推荐引擎
│   ├── regime_engine.py               # 宏观体制状态机引擎 (VIX / HY Spread)
│   ├── risk_guard.py                  # 确定性 Python 硬风控网关 (正股 + 期权风控)
│   └── logger.py                      # 日志基础设施
├── logs/
│   └── audit_trail.jsonl              # 真实交易审计追踪日志 (JSON Lines)
├── sentinel/
│   └── cron_sentinel.py               # 持仓巡检与期权临期平仓守护引擎
├── tests/                             # 自动化单元测试与回测验证套件
│   ├── test_alpaca_client.py          # Alpaca 接口集成单元测试
│   ├── test_fetch_regime_real.py      # 宏观数据拉取与 Regime 测试
│   ├── test_historical_data_validation.py # 回测历史数据质量校验测试
│   ├── test_hybrid_backtester.py      # 混合回测引擎风控与交易逻辑测试
│   ├── test_options_engine.py         # 期权定价、价差与希腊字母计算测试
│   ├── test_regime_engine.py          # 宏观状态机逻辑测试
│   └── test_risk_guard.py             # 硬风控全规则边界与混合资产测试
├── main.py                            # CLI 交互式双轨交易终端主入口
├── run_backtest.py                    # 真实历史行情全资产回测执行脚本
├── pyproject.toml                     # 项目依赖与工具链配置 (uv / pytest)
├── requirements.txt                   # Python 依赖清单
└── README.md                          # 项目说明文档
```

---

## 🚀 快速上手

### 1. 环境准备
推荐使用高性能 Python 包管理器 [uv](https://github.com/astral-sh/uv)：

```powershell
# 克隆仓库
git clone https://github.com/Tonytan123/AiAgentForTrading.git
cd AiAgentForTrading

# 安装并同步项目所有依赖
uv sync
```

### 2. 配置 API 凭证
支持在 `config/settings.yaml` 中配置，或直接设置环境变量：

```powershell
# Alpaca 模拟盘 API Key & Secret Key
$env:ALPACA_API_KEY="你的_ALPACA_KEY"
$env:ALPACA_SECRET_KEY="你的_ALPACA_SECRET"

# Featherless LLM API Key (用于 5 大 Agent 并行辩论与推理)
$env:FEATHERLESS_API_KEY="你的_FEATHERLESS_KEY"

# (可选) 美联储 FRED API Key (用于高收益利差数据)
$env:FRED_API_KEY="你的_FRED_KEY"
```

> 💡 **提示**：若在本地 `config/settings.yaml` 中填入了真实密钥，建议运行 `git update-index --skip-worktree config/settings.yaml` 防止 Git 意外提交敏感配置。

---

## 💻 运行系统

### 1. 启动交互式交易终端 (CLI Terminal)

```powershell
uv run python main.py
```

- **查看大盘与资产**：系统自动同步 Alpaca 账户净值、现金余额、VIX 指数、宏观体制和 S&P 500 标的池行情。
- **选择标的与模式**：输入代码（如 `NVDA`）并选择交易倾向（`AUTO` / `EQUITY` / `OPTION`）。
- **人机协同决策**：查看 5 大 Agent 的详细分析理由、期权价差构建详情与 Critic 审查结果，输入 `A` 确认下单，或 `E` 微调参数。
- **安全退出**：输入 `exit` 或 `q` 随时退出系统。

### 2. 运行股票与期权混合策略历史回测

系统将拉取 30+ 支跨行业核心标的与 VIX 过去 1 年的真实历史日 K 数据，模拟多智能体共识决策、正股持仓与 Bull Call Spread 价差构建，并执行阶梯保本止盈与 Sentinel 临期守护：

```powershell
uv run python run_backtest.py
```

**回测报告输出包含：**
- **数据质量检查**：校验每支标的的有效交易日数、起止日期与历史波动率（HV）。
- **整体组合收益指标**：初始资金、期末净值、总收益率、CAGR、最大回撤、夏普比率（Sharpe）、索提诺比率（Sortino）、总交易笔数与胜率。
- **分资产类型表现拆解**：股票（Equity）与期权价差（Bull Call Spread）的净收益、交易次数、胜率、盈亏比与平均单笔盈亏。
- **出场原因全景归因统计**：`STOCK_TAKE_PROFIT`、`STOCK_STOP_LOSS`、`OPTION_TAKE_PROFIT`、`OPTION_TRAILING_PROFIT`、`OPTION_BREAK_EVEN_PROTECTION`、`OPTION_DTE_EXPIRY_GUARD` 等。

### 3. 运行 15 分钟持仓与期权临期守护引擎 (Cron Sentinel)

在独立后台守护进程运行，保障持仓安全与期权临期平仓：

```powershell
uv run python -c "from sentinel.cron_sentinel import CronSentinel; from alpaca.trading.client import TradingClient; sentinel = CronSentinel(trading_client=TradingClient('KEY', 'SECRET', paper=True)); sentinel.run_daemon()"
```

### 4. 运行全套自动化测试

```powershell
uv run pytest tests/
```

---

## 🐳 Docker 容器化部署与运行

本项目已完整配置轻量化生产级 `Dockerfile` 与 `docker-compose.yml`，支持通过 Docker 或 Docker Compose 在任意容器环境中一键运行。

### 1. 构建 Docker 镜像

```bash
docker build -t aiagentfortrading:latest .
```

### 2. 使用 Docker 一键运行各服务

```bash
# 启动交互式交易终端 (需保持 -it 输入与终端分配)
docker run -it --rm \
  -v ${PWD}/config:/app/config \
  -v ${PWD}/logs:/app/logs \
  -e ALPACA_API_KEY="你的KEY" \
  -e ALPACA_SECRET_KEY="你的SECRET" \
  -e FEATHERLESS_API_KEY="你的FEATHERLESS_KEY" \
  aiagentfortrading:latest python main.py

# 运行历史回测
docker run --rm \
  -v ${PWD}/config:/app/config \
  -v ${PWD}/logs:/app/logs \
  aiagentfortrading:latest python run_backtest.py

# 运行全套测试
docker run --rm aiagentfortrading:latest pytest tests/
```

### 3. 使用 Docker Compose 便捷调度

```bash
# 启动交互式交易终端
docker compose run --rm trader

# 启动历史策略回测
docker compose run --rm backtest

# 启动 15 分钟持仓与期权临期平仓后台守护进程
docker compose up -d sentinel

# 运行自动化测试
docker compose run --rm test
```

---

## ⚙️ 核心风控规则速查

| 风控规则 | 阈值标准 | 触发行为与说明 |
| :--- | :--- | :--- |
| **正股单仓上限** | `<= 10.0%` | 限制单一股票仓位占用总净值比例 |
| **期权单笔权利金** | `<= 2.0%` | 严格限制单一期权价差单笔净支出 |
| **期权总持仓敞口** | `<= 10.0%` | 控制全部期权组合总权利金暴露 |
| **单一板块敞口** | `<= 30.0%` | 基于 GICS 行业分类控制集中度风险 |
| **日内回撤熔断** | `<= 5.0%` | 单日累计浮亏触及阈值全系统熔断开仓 |
| **财报静默期** | `<= 7 天` | 7 天内有二元财报事件一票否决 |
| **期权 DTE 周期** | `14 ~ 60 天` | 严禁 0DTE 末日期权交易，保障充足时间价值 |
| **Sentinel 临期平仓** | `DTE <= 3 天` | 自动平仓锁定价差，彻底规避行权交割与末日流动性风险 |
| **阶梯移动保本止盈** | `+25% / +40%` | 浮盈达 +25% 止损上移至成本价；达 +40% 锁定 +15% 利润 |
| **正股锚定止损** | `-4.0%` | 底层正股价格跌破支撑线时联动平仓期权 |

---

## 📜 许可证

本项目采用 [MIT License](LICENSE) 许可证。

