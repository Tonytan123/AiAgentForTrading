# AiAgentForTrading: Autonomous Multi-Agent Dual-Track Quantitative Trading & Governance System

## 🚀 One-Page Hackathon Submission Write-up

### 1. Project Title & Tagline
- **Project Title:** AiAgentForTrading
- **Tagline:** Autonomous Multi-Agent Consensus Trading Engine with Dual-Track Equity & Options Execution, Trailing Stop Governance, and 24/7 Position Sentinel powered by Alpaca.
- **Technologies Tagged:** `Alpaca Trading API`, `Alpaca Market Data API`, `LangGraph`, `Python`, `Large Language Models (LLM)`, `yfinance`, `FRED API`

---

### 2. Problem Statement
Retail and institutional algorithmic traders face three fundamental dilemmas in modern quantitative markets:
1. **Single-Model Blindspots:** Individual trading strategies fail when market regimes shift (e.g., momentum strategies get crushed in high-volatility sideways regimes; contrarian bets bleed during persistent trends).
2. **Execution Rigidity & High Capital Friction:** Pure equity trading misses asymmetric payoff opportunities, while naive 0DTE options trading suffers severe theta decay and assignment risks.
3. **Lack of Post-Trade Autonomous Governance:** Most trading bots stop after order submission, failing to heal orphan positions, trail stop-losses, monitor DTE expiration risks, or sweep uninvested idle capital.

---

### 3. Solution & Innovation
**AiAgentForTrading** solves these challenges through an end-to-end autonomous multi-agent architecture built natively on **Alpaca API**:

- **Real-Time Macro Regime Adaptation:** Classifies broader markets into `Bull_Trend`, `High_Vol_Bear`, `Panic_Crisis`, and `Neutral_Range` using VIX and FRED High-Yield Spreads, dynamically allocating strategy weights.
- **5-Agent Parallel Consensus Debate (LangGraph StateGraph):**
  - *Momentum Agent* (SMA breakout & volume surges)
  - *Macro Agent* (Systemic risk & yield curves)
  - *StatArb Agent* (SPY correlation & spread Z-Score mean-reversion)
  - *Contrarian Agent* (Panic sentiment & oversold reversals)
  - *Exotic Agent* (Put/Call ratios & 24h cached earnings window analysis)
- **Dual-Track Hybrid Execution (Stock + Bull Call Spread):** Intelligently routes between Bracket OCO stock orders (Take-Profit + Stop-Loss) and defined-risk Bull Call options spreads via Alpaca.
- **24/7 Cron Sentinel & RiskGuard:**
  - *Sentinel DTE Guard:* Automatically closes options with $DTE \le 2$ days to eliminate assignment and expiration liquidity decay.
  - *Orphan OCO Self-Healing:* Audits open stock positions and automatically attaches missing OCO brackets.
  - *Idle Cash Treasury Sweep:* Sweeps idle cash into Treasury ETF ($SGOV) for risk-free APY.
  - *Deterministic RiskGuard:* Code-level hard limits on position sizing, options premium, sector concentration, and daily drawdown.

---

### 4. How Alpaca Powers the Entire Lifecycle
Alpaca serves as the core financial infrastructure across every stage of our system:
1. **Alpaca Market Data API:** Streams real-time stock quotes, historical bars, and options chains to calculate technical indicators and evaluate 5-agent state models.
2. **Alpaca Trading API:**
   - Submits multi-leg Bracket OCO orders (`take_profit` and `stop_loss`).
   - Executes live options limit orders (`ContractType.CALL` spreads).
   - Real-time queries for account equity, buying power, positions, and active orders.
3. **Automated Position Management:** Periodically inspects and auto-closes positions (`close_position`) during sentinel health sweeps.

---

### 5. Key Results & Impact
- **Consensus Quality:** 5-agent parallel voting achieves $\ge 70\%$ weighted agreement threshold before triggering order proposals.
- **Risk Governance:** 100% hard code-level interception of over-allocation and earnings blackout entry.
- **User Experience:** Full bilingual terminal (EN/ZH) with instant runtime switching, rich tabular dashboards, and complete Human-in-the-Loop governance.

---

### 6. Submission Details Checklist
- **Team Repository:** [https://github.com/Tonytan123/AiAgentForTrading](https://github.com/Tonytan123/AiAgentForTrading)
- **Demo Video:** [Insert your YouTube / Loom Video Link here]
- **Alpaca Paper Trading Account ID:** [Insert your Alpaca Paper Account Number / ID here]
