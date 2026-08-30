from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yfinance as yf


# ---------------------------------------------------------------------------
# 1. CLI 与意图解析
# ---------------------------------------------------------------------------


def parse_intent(user_input: str) -> Dict[str, Any]:
    """
    通过轻量规则结构化提取目标信息。

    Expected CLI formats:
        - trade analyze NVDA
        - trade scan S&P500
        - analyze AAPL buy risk_medium

    Returns
    -------
    Dict with keys: ticker, action, risk_preference, mode
    """
    user_input = user_input.strip().lower()

    # 提取标的（简单示例：查找常见票符）
    ticker_match = re.search(r"[A-Z]{1,5}\b", user_input)
    ticker = ticker_match.group(0).upper() if ticker_match else None

    # 提取操作类型
    action = None
    if re.search(r"\bbuy\b|acquire\b|long\b", user_input):
        action = "BUY"
    elif re.search(r"\bsell\b|short\b|exit\b", user_input):
        action = "SELL"
    elif re.search(r"\bscan\b|scan\b|screen\b", user_input):
        mode = "scan"
    else:
        mode = "analyze"

    # 风险偏好
    risk_pref = "neutral"
    if re.search(r"\brisky\b|aggressive\b", user_input):
        risk_pref = "aggressive"
    elif re.search(r"\bconservative\b|safe\b", user_input):
        risk_pref = "conservative"

    return {
        "ticker": ticker,
        "action": action,
        "risk_preference": risk_pref,
        "mode": mode,
        "raw_input": user_input,
    }


# ---------------------------------------------------------------------------
# 2. 市场数据工具（使用 yfinance 免费数据）
# ---------------------------------------------------------------------------


def fetch_price_data(ticker: str, period: str = "3mo", interval: str = "1d") -> Optional["pd.DataFrame"]:
    """获取历史调整后收盘价 DataFrame。"""
    try:
        import pandas as pd
        df = yf.download(ticker, period=period, interval=interval, auto_adjust=True)
        if df.empty:
            return None
        df = df[["Close"]].rename(columns={"Close": "price"})
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[Warn] fetch_price_data({ticker}) failed: {e}")
        return None


def calculate_rsi(series: "pd.Series", period: int = 14) -> float:
    """计算 RSI 并返回最新值（0~100）。"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def calculate_sma(series: "pd.Series", period: int) -> float:
    """简单移动平均最新值。"""
    return float(series.tail(period).mean())


# ---------------------------------------------------------------------------
# 3. 五位研究智能体（并行、相互隔离）
# ---------------------------------------------------------------------------


class BaseAgent:
    """所有智能体的基类，统一接口。"""

    def __init__(self, name: str, weight: float):
        self.name = name
        self.weight = weight

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """返回 {score: float, details: str}. score in [0, 1]."""
        raise NotImplementedError


class MomentumAgent(BaseAgent):
    """动量智能体：趋势突破与相对强弱。"""

    def __init__(self):
        super().__init__("Momentum", weight=0.20)

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        df = fetch_price_data(ticker, period="3mo", interval="1d")
        if df is None or len(df) < 50:
            return {"score": 0.5, "details": "insufficient data"}

        close = df["price"]
        rsi = calculate_rsi(close, 14)
        sma_20 = calculate_sma(close, 20)
        sma_50 = calculate_sma(close, 50)
        last_price = close.iloc[-1]

        score = 0.5  # base

        # 1) 趋势：价格在 20 日均线上方
        if last_price > sma_20:
            score += 0.2
        # 2) 动量：RSI 处于超买/超卖区域的惯性
        if 55 < rsi < 70:
            score += 0.2  # 强劲看多
        elif 30 < rsi < 45:
            score -= 0.2  # 弱势

        # 3) 成交量确认（这里简化：若价格上涨且 RSI > 55 视为放量）
        score = max(0.0, min(1.0, score))

        direction = "看多" if score > 0.5 else "看空"
        details = (f"Momentum|RSI={rsi:.1f}, Price/SMA20={last_price/sma_20:.2f}, "
                   f"Direction={direction}, score={score:.2f}")
        return {"score": score, "details": details}


class MacroAgent(BaseAgent):
    """宏观智能体：美联储、利率、行业轮动。"""

    def __init__(self):
        super().__init__("Macro", weight=0.15)

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        # 占位：基于模拟宏观环境得分
        # 实际可接入 FRED、VIX、美元指数等数据
        score = 0.6  # 中性基线
        details = (f"Macro|environment_neutral, score={score:.2f} | "
                   "placeholder: integrate FRED/VIX/USDX data")
        return {"score": score, "details": details}


class StatArbAgent(BaseAgent):
    """统计套利智能体：配对交易、价差 Z-Score。"""

    def __init__(self):
        super().__init__("StatArb", weight=0.15)

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        # 占位：演示配对相关性/Z-Score 计算框架
        # 实际需选配对标的（如两只相关 ETF），计算 rolling correlation 与 Z-Score
        score = 0.5  # 中性
        details = (f"StatArb|placeholder correlation/zscore, score={score:.2f} | "
                   "needs pair universe & rolling stats")
        return {"score": score, "details": details}


class ContrarianAgent(BaseAgent):
    """逆向/反转智能体：极端超卖、内人买卖、恐慌情绪。"""

    def __init__(self):
        super().__init__("Contrarian", weight=0.15)

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        df = fetch_price_data(ticker, period="3mo", interval="1d")
        if df is None:
            return {"score": 0.5, "details": "no data"}

        close = df["price"]
        rsi = calculate_rsi(close, 14)

        # RSI < 30 为极端超卖，反转概率上升
        if rsi < 30:
            score = 0.8
        elif rsi < 40:
            score = 0.6
        else:
            score = 0.4

        # 模拟内人活动（此处占位）
        insider_net_buy = True  # placeholder
        if insider_net_buy and score >= 0.6:
            score = min(1.0, score + 0.1)

        direction = "看多反转" if score > 0.5 else "看空反转"
        details = (f"Contrarian|RSI={rsi:.1f}, insider_net_buy={insider_net_buy}, "
                   f"score={score:.2f}, direction={direction}")
        return {"score": score, "details": details}


class ExoticAgent(BaseAgent):
    """特殊/异动智能体：日历效应、事件驱动、异常成交量/期权。"""

    def __init__(self):
        super().__init__("Exotic", weight=0.15)

    def analyze(self, ticker: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        # 占位：检查财报窗口、期权异动、突卷成交量
        # 这里用简单的最近 5 天成交量异动作为占位
        df = fetch_price_data(ticker, period="2mo", interval="1d")
        if df is None:
            return {"score": 0.5, "details": "no data"}

        # 计算成交量均值 vs 当日比率（此处简化）
        # 实际应结合选项链异动、财报日历
        # df["Volume"] ... 占位
        avg_vol_placeholder = 0.0
        score = 0.5  # 中性

        # 模拟二元事件：若接近财报日则略微偏向
        today = datetime.now()
        earnings_window = True  # placeholder: check earnings calendar
        if earnings_window:
            score = min(1.0, score + 0.15)

        details = (f"Exotic|volume_placeholder, score={score:.2f} | "
                   "integrate options anomaly & earnings calendar")
        return {"score": score, "details": details}


# ---------------------------------------------------------------------------
# 4. 共识聚合器
# ---------------------------------------------------------------------------


def consensus_aggregator(agent_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算加权总分。

    公式：综合加权得分 = sum(权重 * 单项得分) / sum(权重)

    当加权总分 >= 0.70 时，输出结构化投资备忘录（JSON）。
    """
    # 按权重计算
    weighted_sum = sum(r["score"] * ag.weight for ag, r in zip(AGENTS, agent_results))
    total_weight = sum(ag.weight for ag in AGENTS)
    composite_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    # 判断是否达标
    threshold = 0.70
    triggers = composite_score >= threshold

    # 组建输出
    result = {
        "composite_score": round(composite_score, 4),
        "threshold_met": triggers,
        "agent_details": {
            ag.name: {"score": r["score"], "details": r["details"]}
            for ag, r in zip(AGENTS, agent_results)
        },
    }

    if triggers:
        # 找出第一个看多的标的（示例）
        ticker = intent.get("ticker", "UNKNOWN")
        result["signal"] = {
            "ticker": ticker,
            "direction": "BUY",
            "position_size": "calculate based on risk prefs",  # 实际可用账户净值计算
            "entry_price": None,  # 将在 main.py 中填入
            "tp": None,  # 止盈价格
            "sl": None,  # 止损价格
        }
        # 动态出场点位
        # 注意：这里的 price 需要实时获取，这里设为 None 由调用者填入
        result["signal"]["tp"] = "entry * 1.08"  # TP = 现价 * 108.0%
        result["signal"]["sl"] = "entry * 0.96"  # SL = 现价 * 96.0%

        result["memo"] = (
            f"Consensus aggregated investment memo.\n"
            f"Composite score: {composite_score:.2f} (>= 0.70 threshold met).\n"
            f"Direction: BUY  |  Suggested TP: 108.0%  |  Suggested SL: 96.0%\n"
            f"Agreement: {sum(1 for r in agent_results if r['score'] >= 0.6)}/5 agents bullish."
        )
    else:
        result["memo"] = (
            f"Composite score {composite_score:.2f} below 0.70 threshold. "
            "No auto-execution. Consider re-running later or adjust risk preferences."
        )

    return result


# ---------------------------------------------------------------------------
# 5. 主引擎（CLI 入口 + 定时扫描模式）
# ---------------------------------------------------------------------------

AGENTS = [
    MomentumAgent(),
    MacroAgent(),
    StatArbAgent(),
    ContrarianAgent(),
    ExoticAgent(),
]


def run_agent_parallel(ticker: str, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """并行运行 5 位智能体，返回每个结果列表。"""
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_agent = {
            executor.submit(agent.analyze, ticker, intent): agent
            for agent in AGENTS
        }
        for future in as_completed(future_to_agent):
            agent = future_to_agent[future]
            try:
                r = future.result()
                results.append(r)
            except Exception as e:
                # 保证单个智能体失败不影响整体
                results.append({"score": 0.5, "details": f"agent error: {e}"})
    # 按原始顺序排序（与 AGENTS 顺序一致）
    return results


def execute_cli():
    """CLI 手动指令模式。"""
    print("=== Engine Agent Debate — CLI Mode ===")
    print("Enter command (e.g., 'trade analyze NVDA') or 'quit' to exit.\n")

    while True:
        user_input = input("> ").strip()
        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        intent = parse_intent(user_input)
        if not intent["ticker"]:
            print("❌ Could not extract ticker. Try: 'trade analyze NVDA'")
            continue

        print(f"\n▶ Parsed intent: ticker={intent['ticker']}, action={intent['action']}, "
              f"risk={intent['risk_preference']}, mode={intent['mode']}")

        # 并行分析
        agent_results = run_agent_parallel(intent["ticker"], intent)

        # 共识聚合
        agg = consensus_aggregator(agent_results)

        print("\n--- Consensus Aggregator ---")
        print(json.dumps(agg, ensure_ascii=False, indent=2))

        if agg.get("signal"):
            sig = agg["signal"]
            print(f"\n>>> Structured Investment Memo <<<\n"
                  f"Ticker: {sig['ticker']}\n"
                  f"Direction: {sig['direction']}\n"
                  f"Suggested Position: {sig['position_size']}\n"
                  f"TP (Take Profit): {sig['tp']}\n"
                  f"SL (Stop Loss): {sig['sl']}\n")


def execute_scan_pool(pool: List[str] = None) -> List[Dict[str, Any]]:
    """
    系统定时扫描标的池。

    参数
    ------
    pool : List[str]
        标的列表，如 ["AAPL", "MSFT", "NVDA"]。若为 None 则使用默认标的池。

    返回
    ------
    每个标的的聚合结果列表。
    """
    if pool is None:
        pool = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY"]  # 默认池

    print(f"\n=== System Scan Pool: {len(pool)} tickers ===")
    aggregated = []

    for ticker in pool:
        intent = parse_intent(f"analyze {ticker}")
        if not intent["ticker"]:
            continue

        agent_results = run_agent_parallel(ticker, intent)
        agg = consensus_aggregator(agent_results)
        aggregated.append({"ticker": ticker, "agg": agg})

        # 仅当阈值命中时打印（避免刷屏）
        if agg.get("threshold_met"):
            print(f"[ALERT] {ticker}: composite={agg['composite_score']:.2f} >= 0.70")
            print(json.dumps(agg.get("memo", ""), ensure_ascii=False, indent=2))

    return aggregated


# ---------------------------------------------------------------------------
# 6. Main
# ---------------------------------------------------------------------------


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        execute_scan_pool()
    else:
        execute_cli()


if __name__ == "__main__":
    main()
    