# backtest/backtest_engine.py
import pandas as pd
import numpy as np
from typing import Dict, List, Any

from core.regime_engine import RegimeEngine
from core.risk_guard import RiskGuard
from core.agents.critic_agent import CriticAgent


class Position:
    def __init__(self, ticker: str, shares: int, entry_price: float, entry_date: str, tp_price: float, sl_price: float):
        self.ticker = ticker
        self.shares = shares
        self.entry_price = entry_price
        self.entry_date = entry_date
        self.tp_price = tp_price
        self.sl_price = sl_price
        self.holding_days = 0


class QuantBacktester:
    def __init__(self, config, historical_data: Dict[str, pd.DataFrame], macro_data: pd.DataFrame):
        self.cfg = config
        self.data = historical_data
        self.macro = macro_data
        self.equity = self.cfg.initial_equity
        self.cash = self.cfg.initial_equity
        self.positions: Dict[str, Position] = {}
        
        self.equity_curve: List[Dict[str, Any]] = []
        self.trade_logs: List[Dict[str, Any]] = []

        self.regime_engine = RegimeEngine()
        self.risk_guard = RiskGuard()
        self.critic = CriticAgent()

    def run(self):
        timeline = self.macro.index.sort_values()
        
        for current_date in timeline:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # 1. 获取当日宏观状态并动态调权
            vix = self.macro.loc[current_date, "VIX"]
            hy_spread = self.macro.loc[current_date, "HY_SPREAD"]
            regime = self.regime_engine.determine_regime(vix, hy_spread)
            weights = self.regime_engine.get_strategy_weights(regime)

            # 2. 检查与撮合现有持仓 (OCO 止盈止损 / 超时 28 天平仓)
            self._update_and_settle_positions(current_date, date_str)

            # 3. 计算当日总资产净值
            total_holding_value = sum(
                pos.shares * self._get_price(pos.ticker, current_date, "close")
                for pos in self.positions.values()
            )
            self.equity = self.cash + total_holding_value
            self.equity_curve.append({
                "date": date_str,
                "equity": self.equity,
                "cash": self.cash,
                "holdings_val": total_holding_value,
                "regime": regime
            })

            # 4. 生成新交易信号与风控开仓 (遍历标的池)
            for ticker, df in self.data.items():
                if current_date not in df.index:
                    continue
                if ticker in self.positions:
                    continue

                # 提取特征数据
                bar = df.loc[current_date]
                price = bar["close"]
                rsi = bar.get("rsi", 50.0)
                sma_20 = bar.get("sma_20", price)
                vol_surge = bar.get("vol_surge", 1.0)
                days_to_earn = bar.get("days_to_earnings", 99)

                # Agent 打分逻辑
                mom_score = 0.85 if price > sma_20 and rsi < 70 and vol_surge > 1.2 else 0.40
                macro_score = 0.70 if regime == "RISK-ON" else 0.35
                statarb_score = 0.65
                contra_score = 0.75 if rsi < 35 else 0.45
                exotic_score = 0.70 if days_to_earn > 7 else 0.10

                # 加权共识分计算
                scores = [mom_score, macro_score, statarb_score, contra_score, exotic_score]
                weighted_score = sum(s * w for s, w in zip(scores, weights.values())) / sum(weights.values())

                if weighted_score >= 0.70:
                    proposal = {
                        "proposal_id": f"BT-{date_str}-{ticker}",
                        "ticker": ticker,
                        "action": "BUY",
                        "current_price": price,
                        "suggested_shares": int((self.equity * 0.048) // price),
                        "position_pct": 0.048,
                        "leverage": 1.0,
                        "take_profit_price": round(price * 1.08, 2),
                        "stop_loss_price": round(price * 0.96, 2),
                        "consensus_score": weighted_score
                    }

                    # Critic 独立合规校验
                    critic_passed, _ = self.critic.audit(proposal, list(self.data.keys()), days_to_earn)
                    if not critic_passed:
                        continue

                    # 确定性硬风控校验
                    shares = proposal["suggested_shares"]
                    cost = shares * price * (1.0 + self.cfg.slippage_bps / 10000.0)
                    if cost > self.cash:
                        continue

                    risk_passed, _ = self.risk_guard.validate(
                        order_amount=cost,
                        sector="Technology",
                        total_equity=self.equity,
                        daily_loss_pct=0.0,
                        sector_holdings={}
                    )

                    if risk_passed and shares > 0:
                        self.cash -= cost
                        self.positions[ticker] = Position(
                            ticker=ticker,
                            shares=shares,
                            entry_price=price,
                            entry_date=date_str,
                            tp_price=proposal["take_profit_price"],
                            sl_price=proposal["stop_loss_price"]
                        )

        return self._generate_performance_report()

    def _update_and_settle_positions(self, current_date, date_str: str):
        closed_tickers = []
        for ticker, pos in self.positions.items():
            pos.holding_days += 1
            if current_date not in self.data[ticker].index:
                continue
            
            bar = self.data[ticker].loc[current_date]
            high, low, close = bar["high"], bar["low"], bar["close"]

            exit_price = None
            reason = ""

            # 触发止损 (SL)
            if low <= pos.sl_price:
                exit_price = pos.sl_price * (1.0 - self.cfg.slippage_bps / 10000.0)
                reason = "STOP_LOSS"
            # 触发止盈 (TP)
            elif high >= pos.tp_price:
                exit_price = pos.tp_price * (1.0 - self.cfg.slippage_bps / 10000.0)
                reason = "TAKE_PROFIT"
            # 触发 60 天超时平仓
            elif pos.holding_days >= 60:
                exit_price = close * (1.0 - self.cfg.slippage_bps / 10000.0)
                reason = "TIMEOUT_60D"

            if exit_price:
                pnl = (exit_price - pos.entry_price) * pos.shares
                self.cash += pos.shares * exit_price
                self.trade_logs.append({
                    "ticker": ticker,
                    "entry_date": pos.entry_date,
                    "exit_date": date_str,
                    "entry_price": pos.entry_price,
                    "exit_price": exit_price,
                    "shares": pos.shares,
                    "pnl": pnl,
                    "pnl_pct": (exit_price - pos.entry_price) / pos.entry_price,
                    "reason": reason
                })
                closed_tickers.append(ticker)

        for t in closed_tickers:
            del self.positions[t]

    def _get_price(self, ticker: str, dt, col="close") -> float:
        df = self.data.get(ticker)
        if df is not None and dt in df.index:
            return float(df.loc[dt, col])
        return 0.0

    def _generate_performance_report(self) -> Dict[str, Any]:
        curve_df = pd.DataFrame(self.equity_curve)
        curve_df["returns"] = curve_df["equity"].pct_change().fillna(0)
        
        total_days = len(curve_df)
        total_return = (self.equity - self.cfg.initial_equity) / self.cfg.initial_equity
        cagr = (1 + total_return) ** (252 / total_days) - 1 if total_days > 0 else 0.0
        
        # 最大回撤计算
        curve_df["cummax"] = curve_df["equity"].cummax()
        curve_df["drawdown"] = (curve_df["equity"] - curve_df["cummax"]) / curve_df["cummax"]
        max_drawdown = curve_df["drawdown"].min()

        # 夏普与索提诺比率
        daily_rf = 0.04 / 252
        excess_returns = curve_df["returns"] - daily_rf
        sharpe = np.sqrt(252) * excess_returns.mean() / (curve_df["returns"].std() + 1e-9)
        
        downside_returns = curve_df["returns"][curve_df["returns"] < 0]
        sortino = np.sqrt(252) * excess_returns.mean() / (downside_returns.std() + 1e-9)

        # 胜率与盈亏比
        trades_df = pd.DataFrame(self.trade_logs)
        if not trades_df.empty:
            wins = trades_df[trades_df["pnl"] > 0]
            losses = trades_df[trades_df["pnl"] <= 0]
            win_rate = len(wins) / len(trades_df)
            avg_win = wins["pnl"].mean() if not wins.empty else 0
            avg_loss = abs(losses["pnl"].mean()) if not losses.empty else 1
            pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        else:
            win_rate, pl_ratio = 0.0, 0.0

        return {
            "initial_equity": self.cfg.initial_equity,
            "final_equity": round(self.equity, 2),
            "total_return": f"{total_return:.2%}",
            "cagr": f"{cagr:.2%}",
            "max_drawdown": f"{max_drawdown:.2%}",
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "win_rate": f"{win_rate:.2%}",
            "profit_loss_ratio": round(pl_ratio, 2),
            "total_trades": len(trades_df)
        }