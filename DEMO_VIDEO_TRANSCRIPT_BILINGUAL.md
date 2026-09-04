# 🎬 AiAgentForTrading: Demo Video Script & Storyboard (中英双语对照逐字稿)

**目标时长**: 2分30秒 ~ 3分钟  
**推荐录制工具**: Loom / Windows自带录屏 (`Win + Alt + R`) / OBS  
**适用场景**: Lablab.ai Hackathon 演示视频录制、配音与分镜参考

---

## 🛠️ 录制前准备检查清单

1. **终端字体调大**: 在终端中按 `Ctrl + +` 放大 1~2 级，确保表格渲染清晰。
2. **提前启动两个窗口**:
   - 窗口 1 (主界面): 准备运行 `uv run python main.py -l en`
   - 窗口 2 (守护进程): 准备运行 `uv run python -m sentinel.cron_sentinel -l en`
3. **配音方式建议**:
   - **自己配音**: 对照下方英文台词以稳健、自信语速朗读；
   - **AI配音**: 录完无声视频后，复制英文台词至剪映电脑版（文本朗读）或 ElevenLabs 自动合成。

---

## ⏱️ 分镜脚本与中英对照逐字稿

### 🎬 Scene 1: 开场与痛点阐述 (0:00 - 0:30)
- **🖥️ 屏幕画面**: 打开浏览器展示 GitHub 仓库首页 (`AiAgentForTrading`)，展示项目 16:9 封面图、Alpaca 标签与架构流程图。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"Hello judges! Welcome to **AiAgentForTrading** — an autonomous multi-agent quantitative trading and risk governance platform powered by the **Alpaca Trading API**, **LangGraph**, and LLMs.*  
  >  
  > *Most trading bots fail when market regimes shift, and they completely lack post-trade position governance. Today, we’ll show you how our 5-agent consensus engine and automated Alpaca execution solve this end-to-end."*
- **📖 中文对照释义**:
  > 评委好！欢迎观看 AiAgentForTrading 的演示——这是一个基于 Alpaca API、LangGraph 与大模型构建的全流程量化交易与风控治理系统。多数量化工具在市场体制转换时容易失效且缺乏持仓治理，今天我们将展示系统如何实现全流程闭环。

---

### 🎬 Scene 2: 启动终端与 Alpaca 实时数据同步 (0:30 - 1:00)
- **🖥️ 屏幕操作**: 切换到终端，输入并运行：
  ```powershell
  uv run python main.py -l en
  ```
  展示实时的 **Account Overview**、**Positions Table（当前持仓）** 和 **Open Orders Table（未成交挂单）**。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"Let’s launch our interactive CLI terminal.*  
  >  
  > *On startup, the system directly syncs with the **Alpaca API** to pull live portfolio equity, buying power, open positions, and active orders.*  
  >  
  > *Simultaneously, our **Macro Regime Engine** evaluates real-time VIX volatility and High-Yield credit spreads to identify the current market state as `Bull_Trend`, dynamically adjusting our 5 agents' voting weights."*
- **📖 中文对照释义**:
  > 启动交易终端，系统第一时间连接 Alpaca API 同步净值、持仓和活动挂单。同时宏观体制引擎结合实时 VIX 与信用利差判定市场为多头趋势，并动态调整五大智能体的权重。

---

### 🎬 Scene 3: 五大智能体实时协商扫盘 (1:00 - 1:40)
- **🖥️ 屏幕操作**: 在终端提示符处输入字母 `S` 并按回车：
  ```text
  S
  ```
  展示 5 个 Agent 并行辩论打分，高亮呈现生成的 **S&P 500 Scanner Leaderboard**（标有 `[POSITION]`、`[PENDING]`、`[NEW]` 徽标）。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"Now, let's trigger our full-market **5-Agent Consensus Scanner** by typing `S`.*  
  >  
  > *Under the hood, **LangGraph** coordinates 5 research agents running in parallel: Momentum, Macro, StatArb, Contrarian, and Exotic Agent — which audits our 24-hour cached earnings calendar to veto binary risk.*  
  >  
  > *Only opportunities with a weighted consensus score $\ge 70\%$ make it to this leaderboard, with intelligent status badges so we never chase existing positions."*
- **📖 中文对照释义**:
  > 输入 S 触发全市场五智能体扫盘。LangGraph 调度动量、宏观、套利、逆向与衍生品 5 大智能体并行辩论，结合 24 小时财报日历避开二元风险。只有得分 $\ge 70\%$ 的机会才会上榜，并自动标记持仓状态防止追高。

---

### 🎬 Scene 4: 投资备忘录与 Alpaca 真实下单 (1:40 - 2:20)
- **🖥️ 屏幕操作**: 输入推荐榜单中的序号（如输入 `1`），展示弹出的 **Hybrid Investment Memo Panel**；随后在 HitL 提示符中输入 `A` 确认审批，展示绿色成功的 Alpaca 下单回执与审计日志写入。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"Let's select the top recommendation.*  
  >  
  > *The system generates a **Hybrid Investment Memo** and passes it to an independent **Critic Agent** and deterministic Python **RiskGuard** to enforce hard position and sector limits.*  
  >  
  > *In our Human-in-the-Loop flow, we can fine-tune parameters or simply press `A` to approve.*  
  >  
  > *Instantly, a multi-leg Bracket OCO order with predefined profit targets and stop-losses is dispatched directly to the **Alpaca Trading API**."*
- **📖 中文对照释义**:
  > 选中排名第一的标的，系统生成正股/期权投资备忘录，经由独立审查员与硬风控校验。在人机审批中按 A 确认，系统立即向 Alpaca API 下发带有止盈止损的 Bracket OCO 订单。

---

### 🎬 Scene 5: 24/7 Sentinel 守护与中英文双语切换 (2:20 - 2:45)
- **🖥️ 屏幕操作**:
  1. 在主菜单输入 `L`，展示界面瞬间切换为中文；再输入 `L` 切回英文。
  2. 在右侧终端运行守护命令：
     ```powershell
     uv run python -m sentinel.cron_sentinel -l en
     ```
     展示 Sentinel 自动检查持仓、期权 DTE 临期平仓与闲置资金清扫买入 SGOV 国债 ETF。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"With full bilingual i18n support, operators can press `L` to switch seamlessly between English and Chinese.*  
  >  
  > *Post-trade, our **Cron Sentinel** runs 24/7 in the background: it automatically attaches missing OCO brackets to orphan positions, market-closes options with DTE $\le 2$ days before theta cliff, and sweeps idle cash into Treasury ETF ($SGOV) for risk-free APY."*
- **📖 中文对照释义**:
  > 系统支持按 L 键在中英文之间毫秒级切换。在后台，Sentinel 守护引擎 24 小时巡检：补齐缺失的 OCO 保护单、在期权到期前两天自动平仓锁定收益，并将闲置资金买入超短期国债 ETF。

---

### 🎬 Scene 6: 结语致谢 (2:45 - 3:00)
- **🖥️ 屏幕画面**: 切回 GitHub 页面，展示 README 上的封面图与测试通过报告。
- **🎙️ 英文旁白 (English Voiceover)**:
  > *"AiAgentForTrading combines multi-agent intelligence with institutional risk governance on Alpaca.*  
  >  
  > *Thank you for watching, and feel free to explore our code on GitHub!"*
- **📖 中文对照释义**:
  > AiAgentForTrading 将多智能体 AI 与 Alpaca 机构级风控执行完美结合。感谢观看，欢迎在 GitHub 上体验我们的开源代码！

---

## 📤 提交交付速查
- **YouTube 格式建议**: 标题 `AiAgentForTrading - Autonomous Multi-Agent Trading on Alpaca`，可见性选择 **Unlisted**（不公开）。
- **Loom 格式建议**: 录制完成后直接复制生成的 Share Link。
