# 🎬 AiAgentForTrading: Hackathon Demo Video Script

**Target Duration:** 2:30 - 3:00 Minutes  
**Tone:** Confident, professional, energetic, and clear  
**Recording Tool:** Loom / OBS / Windows Game Bar (`Win + Alt + R`)

---

## ⏱️ Timeline & Scene-by-Scene Script

### Scene 1: Introduction & Problem Statement (0:00 - 0:30)
**🖥️ On-Screen Action:**  
Show the project title slide or GitHub repository (`AiAgentForTrading`) with Alpaca and LangGraph logos.

**🎙️ Voiceover (English):**  
> *"Hello everyone! Welcome to the demo of **AiAgentForTrading** — an autonomous multi-agent quantitative trading and risk governance system built on the **Alpaca API**, **LangGraph**, and Large Language Models.*  
>  
> *Modern retail and quantitative traders struggle with single-model blind spots when market regimes shift, rigid execution that misses asymmetric options payoffs, and a total lack of post-trade position governance.*  
>  
> *Today, we're showing you how our 5-agent consensus engine and automated Alpaca execution solve this completely."*

---

### Scene 2: Interactive Terminal & Real-Time Alpaca Sync (0:30 - 1:00)
**🖥️ On-Screen Action:**  
Open the terminal and run:
```powershell
uv run python main.py -l en
```
Highlight the live Alpaca Account Overview, Current Positions table, and Open Orders table rendering with rich formatting.

**🎙️ Voiceover (English):**  
> *"Let’s launch our interactive trading terminal.  
>  
> Right on startup, the system connects to the **Alpaca API** to fetch real-time portfolio equity, available buying power, open positions, and active orders.  
>  
> Simultaneously, our **Macro Regime Engine** evaluates live VIX volatility and Federal Reserve High-Yield credit spreads to classify the market state — in this case, `Bull_Trend` — and automatically adjusts our multi-agent strategy weights."*

---

### Scene 3: 5-Agent Consensus Market Scanner (1:00 - 1:40)
**🖥️ On-Screen Action:**  
In the terminal, type:
```text
S
```
Show the 5 agents debating across S&P 500 assets, followed by the generated Market Scanner table showing scores, regime, and status badges (`[POSITION]`, `[PENDING]`, `[NEW]`).

**🎙️ Voiceover (English):**  
> *"Now, let's trigger our full-market **5-Agent Consensus Scanner** by typing `S`.  
>  
> Under the hood, **LangGraph** coordinates 5 specialized research agents running in parallel:  
> - **Momentum Agent** analyzing trend breakouts and volume,  
> - **Macro Agent** checking systemic risk,  
> - **StatArb Agent** calculating SPY correlation and Z-score mean reversion,  
> - **Contrarian Agent** scouting oversold reversals, and  
> - **Exotic Agent** auditing options flow and our 24-hour cached earnings calendar to prevent binary event risk.  
>  
> Only opportunities with a weighted consensus score above 70% make it to this leaderboard, clearly tagged so we never chase existing positions."*

---

### Scene 4: Hybrid Investment Memo & Alpaca Order Execution (1:40 - 2:20)
**🖥️ On-Screen Action:**  
Select a recommended item index (e.g., `1` or type `NVDA`).  
Show the **Hybrid Investment Memo Panel** with entry price, stop-loss, take-profit, and asset selection (Common Stock Bracket OCO or Bull Call Options Spread).  
Press `A` to Approve.  
Show the green success message: Order submitted to Alpaca with immutable audit trail.

**🎙️ Voiceover (English):**  
> *"Let's select the top opportunity.  
>  
> The system synthesizes a **Hybrid Investment Memo** and passes it through an independent **Critic Agent** and deterministic Python **RiskGuard** to enforce strict position limits and earnings blackout periods.  
>  
> In our Human-in-the-Loop governance flow, we can fine-tune parameters or hit `A` to approve.  
>  
> Instantly, the order is dispatched via the **Alpaca Trading API** — submitting a multi-leg Bracket OCO order with automated take-profit and stop-loss levels, and logging every action to an immutable audit trail."*

---

### Scene 5: 24/7 Cron Sentinel & Bilingual Support (2:20 - 2:50)
**🖥️ On-Screen Action:**  
1. In the terminal, type `L` to show instant bilingual UI translation to Chinese, and `L` again back to English.  
2. Open a second split terminal and run:
```powershell
uv run python -m sentinel.cron_sentinel -l en
```
Show Sentinel auto-healing OCO orders, checking options DTE $\le 2$ days for auto-exit, and sweeping idle cash into SGOV Treasury ETF.

**🎙️ Voiceover (English):**  
> *"Post-trade, our **Cron Sentinel** runs 24/7 in the background. It monitors options DTE to auto-close expiring contracts, heals orphan positions with fresh OCO brackets, and sweeps idle cash into ultra-short Treasury ETFs for risk-free yield.  
>  
> Plus, with full bilingual internationalization, operators can seamlessly toggle between English and Chinese on the fly with a single keystroke."*

---

### Scene 6: Conclusion (2:50 - 3:00)
**🖥️ On-Screen Action:**  
Show the GitHub repo link and closing slide with Alpaca, Lablab.ai, and Team info.

**🎙️ Voiceover (English):**  
> *"AiAgentForTrading bridges cutting-edge Multi-Agent AI with institutional-grade risk management and execution on Alpaca.  
>  
> Thank you for watching, and check out our open-source repo on GitHub!"*

---

## 💡 Quick Tips for the Recording

1. **Terminal Font Size:** Increase your terminal font size slightly (`Ctrl + +`) so text, tables, and colors are crisp on video.
2. **Audio:** Speak at a steady, confident pace. If using Loom, the webcam bubble in the bottom corner adds a great personal touch!
3. **No Retake Stress:** You don't need a Hollywood production — showing the live CLI running real Alpaca API interactions is what judges love to see.
