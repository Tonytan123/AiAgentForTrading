# AiAgentForTrading

基于 **Alpaca API**、**LangGraph 多智能体协同状态图** 与 **大语言模型（LLM）** 的全流程量化交易决策、期权双轨执行与风险治理系统。

系统集成了 **实时宏观体制检测（Market Regime）**、**5 大策略研究智能体并行辩论与共识**、**正股/期权混合资产提案生成（Hybrid Memo）**、**独立 Critic 审查**、**CLI 人机协同决策治理（Human-in-the-Loop）**、**确定性硬风控拦截（RiskGuard）**、**15分钟持仓与期权临期守护引擎（Cron Sentinel）** 以及 **全流程事件驱动回测引擎（Backtest Engine）**。

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
  - 依据宏观模式动态调配 5 大策略的权重矩阵。
- **正股 + Alpaca 期权双轨资产决策 (Hybrid Investment Memo)**：
  - 支持 **正股配置（Common Stock）** 与 **标准期权（Standard Long Call / Put）** 混合决策。
  - 智能资产选择：支持 `AUTO` 智能路由、`EQUITY`（仅正股）与 `OPTION`（仅期权）。
  - 完整期权建模：包含 OCC 标准合约代码、行权价、到期日、DTE、希腊字母（Delta、Theta、IV）及权利金预算限制。
- **双重风控防御体系**：
  - **Critic 独立合规审查**：校验 S&P 500 白名单、期权 DTE 周期约束 (14 ~ 60天)、权利金成本上限 (<=2.0%) 以及 7 天二元财报事件一票否决。
  - **确定性 Python 硬风控 (RiskGuard)**：不依赖 LLM，代码级拦截正股单仓上限 (10%)、期权单笔权利金 (2.0%)、期权总敞口 (10.0%)、板块集中度 (30%) 及日内浮亏熔断 (5%)。
- **人机协同终端治理 (HitL CLI Terminal)**：
  - 丰富的富文本交互看板（`rich`），支持连续分析决策（REPL 循环）。
  - 支持分资产类型参数微调（正股股数 vs 期权张数与止盈止损）。
  - 一键执行审批 (`A`)、驳回 (`R`)、微调参数 (`E`) 或跳过 (`S`)，审批通过后自动下发 Bracket OCO 或期权限价单。
- **15 分钟持仓与期权临期守护引擎 (Cron Sentinel)**：
  - **期权临期平仓**：自动识别期权持仓，当 `DTE <= 2` 天时强制市价平仓，规避行权交割风险。
  - **孤儿持仓对冲**：定期巡检正股持仓，自动补齐缺失的止盈止损挂单。
  - **超时持仓平仓**：单笔正股最大持仓周期（180天）超时强制平仓。
- **不可变审计追踪 (Audit Trail)**：
  - 所有订单下发、参数变更与持仓自愈记录均写入不可篡改的 `logs/audit_trail.jsonl`。
- **历史回测系统 (Backtest Engine)**：
  - 支持对多标的、多 Agent 模拟共识与风控拦截的历史表现进行全流程回测与统计。

---

## 🏗️ 系统架构流程

```mermaid
flowchart TD
    A[启动主交互终端 main.py] --> B[同步 Alpaca 账户 & 实时宏观指标 VIX / HY Spread]
    B --> C[Regime Engine 裁定宏观体制并分配策略权重]
    C --> D[拉取 S&P 500 标的池实时行情快照]
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
├── backtest/                      # 回测系统模块
│   ├── backtest_engine.py         # 事件驱动回测核心引擎
│   └── config.py                  # 回测参数配置与数据结构
├── cli/
│   └── terminal_ui.py             # 终端富文本渲染面板 (Rich Hybrid Memo Panel)
├── config/
│   ├── settings.yaml              # 全局系统配置 (Alpaca / Featherless / 风控阈值)
│   ├── investment_memo.yaml       # Critic 独立审查合规规则 (正股 + 期权)
│   └── sp500_universe.json        # 标普 500 核心标的池白名单
├── core/
│   ├── agents/                    # 5 大策略研究 Agent 与 Critic Agent
│   │   ├── base_agent.py          # 智能体基类 (抽象评估接口与 LLM 封装)
│   │   ├── momentum_agent.py      # 动量趋势智能体
│   │   ├── macro_agent.py         # 宏观基本面智能体
│   │   ├── statarb_agent.py       # 统计套利智能体
│   │   ├── contrarian_agent.py    # 逆向反转智能体
│   │   ├── exotic_agent.py        # 衍生品与事件驱动智能体
│   │   └── critic_agent.py        # 独立审查智能体 (一票否决权)
│   ├── alpaca_client.py           # Alpaca API 统一网关客户端 (正股 + 期权交易与行情)
│   ├── consensus_engine.py        # 基于 LangGraph 的多智能体共识与混合资产决策引擎
│   ├── options_engine.py          # 期权定价与选择引擎
│   ├── regime_engine.py           # 宏观体制状态机引擎 (VIX / HY Spread)
│   ├── risk_guard.py              # 确定性 Python 硬风控网关 (正股 + 期权风控)
│   └── logger.py                  # 日志基础设施
├── logs/
│   └── audit_trail.jsonl          # 真实交易审计追踪日志 (JSON Lines)
├── sentinel/
│   └── cron_sentinel.py           # 15 分钟持仓巡检与期权临期平仓守护引擎
├── tests/                         # 完整的自动化测试套件
│   ├── test_alpaca_client.py      # Alpaca 接口集成单元测试
│   ├── test_fetch_regime_real.py  # 宏观数据拉取与 Regime 测试
│   ├── test_regime_engine.py      # 宏观状态机逻辑测试
│   └── test_risk_guard.py         # 硬风控全规则边界与混合资产测试
├── main.py                        # CLI 交互式双轨交易终端主入口
├── run_backtest.py                # 回测执行入口脚本
├── pyproject.toml                 # 项目依赖与工具链配置 (uv / pytest)
├── requirements.txt               # Python 依赖清单
└── README.md                      # 项目说明文档
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

- **查看大盘与资产**：系统自动同步 Alpaca 账户净值、现金余额、VIX 指数、宏观体制和 S&P 500 标的池行情（网络不通时自动启用 $100,000 离线模拟模式）。
- **选择标的与模式**：输入代码（如 `NVDA`）并选择交易倾向（`AUTO` / `EQUITY` / `OPTION`）。
- **人机协同决策**：查看 5 大 Agent 的详细分析理由与 Critic 审查结果，输入 `A` 确认下单，或 `E` 微调参数。
- **安全退出**：输入 `exit` 或 `q` 随时退出系统。

### 2. 运行 15 分钟持仓与期权临期守护引擎 (Cron Sentinel)

在独立后台守护进程运行，保障持仓安全与期权临期平仓：

```powershell
uv run python -c "from sentinel.cron_sentinel import CronSentinel; from alpaca.trading.client import TradingClient; sentinel = CronSentinel(trading_client=TradingClient('KEY', 'SECRET', paper=True)); sentinel.run_daemon()"
```

### 3. 运行策略历史回测

```powershell
uv run python run_backtest.py
```

### 4. 运行自动化测试套件

```powershell
uv run pytest tests/test_risk_guard.py tests/test_regime_engine.py
```

---

## ⚙️ 核心风控规则速查

| 风控规则 | 阈值标准 | 说明 |
| :--- | :--- | :--- |
| **正股单仓上限** | `<= 10.0%` | 防止单一股票仓位过重 |
| **期权单笔权利金** | `<= 2.0%` | 限制衍生品单笔损失暴露 |
| **期权总持仓敞口** | `<= 10.0%` | 控制全部期权保证金与权利金总占用 |
| **单一板块敞口** | `<= 30.0%` | 避免行业集中度风险 |
| **日内回撤熔断** | `<= 5.0%` | 单日累计浮亏触及阈值全系统熔断开仓 |
| **财报静默期** | `<= 7 天` | 7 天内有二元财报事件一票否决 |
| **期权 DTE 周期** | `14 ~ 60 天` | 严禁 0DTE 末日期权交易 |
| **期权临期强制平仓**| `DTE <= 2 天` | 守护巡检自动市价平仓规避行权交割 |

---

## 📜 许可证

本项目采用 [MIT License](LICENSE) 许可证。
