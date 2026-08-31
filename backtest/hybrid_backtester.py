"""
backtest/hybrid_backtester.py
正股与 Alpaca 期权双轨量化策略回测引擎 (含 Bull Call Spread 牛市看涨价差与高置信度事件驱动)
"""

import math
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from scipy.stats import norm

from core.options_engine import black_scholes_price


# ==========================================
# 1. 持仓模型定义 (正股 vs 期权价差)
# ==========================================
class HybridPosition:
    def __init__(
        self,
        asset_type: str,            # 'EQUITY' or 'OPTION'
        ticker: str,
        entry_date: str,
        qty: int,                   # 股数 (正股) 或 组数 (期权价差组数)
        entry_price: float,         # 买入均价 (正股现价 或 期权价差净权利金 Net Debit)
        tp_price: float,            # 止盈触发价
        sl_price: float,            # 止损触发价
        option_type: Optional[str] = None, # 'Call', 'Put', 'BullCallSpread'
        strike: Optional[float] = None,    # 买入腿行权价 K1
        strike_short: Optional[float] = None, # 卖出腿行权价 K2
        initial_dte: Optional[int] = None,
        iv: Optional[float] = None,
        entry_dt: Optional[pd.Timestamp] = None,
        expiry_dt: Optional[pd.Timestamp] = None,
        entry_stock_price: Optional[float] = None
    ):
        self.asset_type = asset_type
        self.ticker = ticker
        self.entry_date = entry_date
        self.qty = qty
        self.entry_price = entry_price
        self.tp_price = tp_price
        self.sl_price = sl_price
        self.entry_stock_price = entry_stock_price if entry_stock_price is not None else entry_price

        self.option_type = option_type or "BullCallSpread"
        self.strike = strike
        self.strike_short = strike_short
        self.initial_dte = initial_dte if initial_dte is not None else 0
        self.remaining_dte = self.initial_dte
        self.iv = iv if iv is not None else 0.35
        self.holding_days = 0

        # 时间戳精确跟踪 (支持自然日日历到期计算)
        self.entry_dt = entry_dt if entry_dt is not None else pd.to_datetime(entry_date)
        if expiry_dt is not None:
            self.expiry_dt = expiry_dt
        elif initial_dte is not None:
            self.expiry_dt = self.entry_dt + pd.Timedelta(days=initial_dte)
        else:
            self.expiry_dt = self.entry_dt


# ==========================================
# 2. 双轨策略回测主引擎
# ==========================================
class HybridStrategyBacktester:
    def __init__(
        self,
        market_data: Dict[str, pd.DataFrame],
        vix_series: pd.Series,
        initial_equity: float = 100000.0,
        risk_free_rate: float = 0.045,
        slippage_bps: float = 5.0,
        stock_budget_pct: float = 0.08,    # 正股单仓上限 8%
        option_budget_pct: float = 0.015,   # 期权单笔净权利金 <= 1.5%
        stock_timeout_days: int = 28,
        dte_guard_threshold: int = 3,       # 临期守护阈值 (自然日 DTE <= 3)
        option_tp_pct: float = 0.60,        # 期权价差止盈 +60%
        option_sl_pct: float = 0.50,        # 期权价差最大止损 -50% (兜底风控)
        stock_tp_pct: float = 0.08,         # 正股止盈 +8%
        stock_sl_pct: float = 0.04          # 正股止损 -4%
    ):
        self.market_data = market_data
        self.vix_series = vix_series
        self.initial_equity = initial_equity
        self.equity = initial_equity
        self.cash = initial_equity
        self.r = risk_free_rate
        self.slippage = slippage_bps / 10000.0
        self.stock_budget_pct = stock_budget_pct
        self.option_budget_pct = option_budget_pct
        self.stock_timeout_days = stock_timeout_days
        self.dte_guard_threshold = dte_guard_threshold
        self.option_tp_pct = option_tp_pct
        self.option_sl_pct = option_sl_pct
        self.stock_tp_pct = stock_tp_pct
        self.stock_sl_pct = stock_sl_pct

        self.positions: List[HybridPosition] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.closed_trades: List[Dict[str, Any]] = []

    def _calc_spread_price(self, s: float, k1: float, k2: Optional[float], dte: int, iv: float) -> float:
        """计算牛市看涨价差 (Bull Call Spread: Long K1 Call - Short K2 Call) 理论净价值"""
        p1 = black_scholes_price(s, k1, dte, self.r, iv, "call")
        if k2 is not None and k2 > k1:
            p2 = black_scholes_price(s, k2, dte, self.r, iv, "call")
            return max(0.01, float(p1 - p2))
        return max(0.01, float(p1))

    def run(self) -> Dict[str, Any]:
        common_dates = self.vix_series.index.sort_values()

        for dt in common_dates:
            dt_ts = pd.to_datetime(dt)
            date_str = dt_ts.strftime("%Y-%m-%d")
            vix = float(self.vix_series.loc[dt])
            regime = "RISK-OFF" if vix > 20.0 else "RISK-ON"

            # 1. 每日持仓检查与撮合出场 (TP/SL/DTE守护)
            self._process_daily_settlement(dt, date_str)

            # 闲置现金计入每日无风险收益 (国债/货币基金年化 4.5%)
            if self.cash > 0:
                self.cash += self.cash * (self.r / 252.0)

            # 2. 计算当前组合总资产净值 (Cash + 正股市值 + 期权估值)
            current_portfolio_val = self._evaluate_current_portfolio(dt)
            self.equity = self.cash + current_portfolio_val

            self.equity_curve.append({
                "date": date_str,
                "equity": self.equity,
                "cash": self.cash,
                "portfolio_val": current_portfolio_val,
                "regime": regime,
                "open_positions": len(self.positions)
            })

            # 3. 扫描标的池寻找开仓机会
            held_tickers = {p.ticker for p in self.positions}
            for ticker, df in self.market_data.items():
                if ticker in held_tickers or dt not in df.index:
                    continue

                bar = df.loc[dt]
                price = float(bar["close"])
                rsi = float(bar.get("rsi", 50.0))
                sma_20 = float(bar.get("sma_20", price))
                vol_surge = float(bar.get("vol_surge", 1.0))
                iv = max(0.20, float(bar.get("iv_proxy", 0.35)))
                days_to_earn = float(bar.get("days_to_earnings", 30))

                # 5 大智能体辩论评分模拟
                # 动量评分：趋势明确且突破放量
                if price > sma_20 and rsi < 70 and vol_surge > 1.25:
                    mom_score = 0.95 if (55 <= rsi <= 66) else 0.88
                else:
                    mom_score = 0.40

                macro_score = 0.85 if regime == "RISK-ON" else 0.30
                statarb_score = 0.70
                
                if rsi < 35:
                    contra_score = 0.75
                elif price > sma_20 and (55 <= rsi <= 66) and vol_surge > 1.25:
                    contra_score = 0.75  # 顺势共识
                elif price > sma_20 and vol_surge > 1.2:
                    contra_score = 0.50
                else:
                    contra_score = 0.40

                exotic_score = 0.75 if days_to_earn > 7 else 0.10

                weights = [0.80, 0.60, 0.60, 0.70, 0.60] if regime == "RISK-ON" else [0.40, 0.80, 0.80, 0.20, 0.20]
                scores = [mom_score, macro_score, statarb_score, contra_score, exotic_score]
                consensus_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

                # 共识阈值 >= 0.70 触发开仓
                if consensus_score >= 0.70:
                    # 极度严苛的【高胜率狙击期权规则】：
                    # 1. 宏观极度安全: RISK-ON 且 VIX < 16.5
                    # 2. 动量处于黄金突破初段: 55 <= RSI <= 65, 放量 vol_surge >= 1.35 且未超买
                    # 3. 规避财报黑天鹅与 IV 骤降: 距离财报日 >= 14 天
                    # 4. 5 大智能体加权共识分 >= 0.80 且标的高于均线 0.5%
                    is_option_trade = (
                        regime == "RISK-ON"
                        and vix < 16.5
                        and consensus_score >= 0.80
                        and (55 <= rsi <= 65)
                        and vol_surge >= 1.35
                        and days_to_earn >= 14
                        and price > sma_20 * 1.005
                    )

                    if is_option_trade:
                        # ---- 高胜率平值牛市价差 (ATM Bull Call Spread: 买入 ATM K1 Call，卖出 OTM +5% K2 Call 对冲 Theta) ----
                        k1 = round(price * 1.00, 1)  # 买入腿 K1 (平值 ATM，具有充足的 Delta 弹性)
                        k2 = round(price * 1.05, 1)  # 卖出腿 K2 (上方 5% 卖出，大幅压降开仓成本与 Theta 损耗)
                        dte = 28
                        net_debit = self._calc_spread_price(price, k1, k2, dte, iv)
                        contract_cost = net_debit * 100

                        # 硬风控: 单笔净权利金 <= 1.5%
                        budget = self.equity * self.option_budget_pct
                        contracts = max(1, int(budget // contract_cost)) if contract_cost > 0 else 0
                        total_cost = contracts * contract_cost

                        if total_cost <= self.cash and contracts > 0:
                            self.cash -= total_cost
                            self.positions.append(HybridPosition(
                                asset_type="OPTION",
                                ticker=ticker,
                                entry_date=date_str,
                                qty=contracts,
                                entry_price=net_debit,
                                tp_price=round(net_debit * (1.0 + self.option_tp_pct), 2),  # 价差止盈 +50%~+60%
                                sl_price=round(net_debit * (1.0 - self.option_sl_pct), 2),  # 价差止损 -50%
                                option_type="BullCallSpread",
                                strike=k1,
                                strike_short=k2,
                                initial_dte=dte,
                                iv=iv,
                                entry_dt=dt_ts,
                                expiry_dt=dt_ts + pd.Timedelta(days=dte),
                                entry_stock_price=price
                            ))
                    else:
                        # ---- 正股稳健主力策略: Bracket OCO, 单仓 <= 8.0% ----
                        budget = self.equity * self.stock_budget_pct
                        shares = int(budget // price)
                        total_cost = shares * price * (1.0 + self.slippage)

                        if total_cost <= self.cash and shares > 0:
                            self.cash -= total_cost
                            self.positions.append(HybridPosition(
                                asset_type="EQUITY",
                                ticker=ticker,
                                entry_date=date_str,
                                qty=shares,
                                entry_price=price,
                                tp_price=round(price * (1.0 + self.stock_tp_pct), 2),  # 正股 TP: +8%
                                sl_price=round(price * (1.0 - self.stock_sl_pct), 2),  # 正股 SL: -4%
                                entry_dt=dt_ts,
                                entry_stock_price=price
                            ))

        return self._calculate_performance_metrics()

    def _process_daily_settlement(self, dt, date_str: str):
        current_dt = pd.to_datetime(dt)
        remaining = []
        for pos in self.positions:
            pos.holding_days += 1
            if pos.ticker not in self.market_data or dt not in self.market_data[pos.ticker].index:
                remaining.append(pos)
                continue

            bar = self.market_data[pos.ticker].loc[dt]
            high, low, close = float(bar["high"]), float(bar["low"]), float(bar["close"])
            iv = max(0.20, float(bar.get("iv_proxy", 0.35)))

            exit_flag = False
            exit_price = 0.0
            exit_reason = ""
            current_spread_val = 0.0

            if pos.asset_type == "EQUITY":
                if low <= pos.sl_price:
                    exit_price = pos.sl_price
                    exit_flag = True
                    exit_reason = f"STOCK_STOP_LOSS (-{int(self.stock_sl_pct*100)}%)"
                elif high >= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_flag = True
                    exit_reason = f"STOCK_TAKE_PROFIT (+{int(self.stock_tp_pct*100)}%)"
                elif pos.holding_days >= self.stock_timeout_days:
                    exit_price = close
                    exit_flag = True
                    exit_reason = f"STOCK_TIMEOUT_{self.stock_timeout_days}D"

                if exit_flag:
                    self.cash += pos.qty * exit_price
                    pnl = (exit_price - pos.entry_price) * pos.qty
                    self.closed_trades.append({
                        "ticker": pos.ticker,
                        "asset_type": "EQUITY",
                        "entry_date": pos.entry_date,
                        "exit_date": date_str,
                        "holding_days": pos.holding_days,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": (exit_price - pos.entry_price) / (pos.entry_price + 1e-9),
                        "reason": exit_reason
                    })
                else:
                    remaining.append(pos)

            elif pos.asset_type == "OPTION":
                if pos.expiry_dt is not None:
                    pos.remaining_dte = max(0, (pos.expiry_dt - current_dt).days)
                else:
                    pos.remaining_dte = max(0, pos.remaining_dte - 1)

                current_spread_val = self._calc_spread_price(
                    close, pos.strike, pos.strike_short, pos.remaining_dte, iv
                )

                # 动态跟踪持仓期间达到的最高价差估值
                pos.highest_opt_val = max(getattr(pos, "highest_opt_val", pos.entry_price), current_spread_val)
                gain_from_entry = (pos.highest_opt_val - pos.entry_price) / (pos.entry_price + 1e-9)

                # 阶梯保本 / 移动止盈机制：
                # 1. 浮盈曾达到 +40%：止损线上移至锁定 +15% 利润 (上移至 entry_price * 1.15)
                if gain_from_entry >= 0.40:
                    pos.sl_price = max(pos.sl_price, round(pos.entry_price * 1.15, 2))
                # 2. 浮盈曾达到 +25%：止损线上移至进场成本价 (Break-Even 0%，保证不亏出场)
                elif gain_from_entry >= 0.25:
                    pos.sl_price = max(pos.sl_price, round(pos.entry_price * 1.00, 2))

                # 1. Sentinel 临期守护机制（第一优先级）：DTE <= 阈值自动平仓锁定剩余价差
                if pos.remaining_dte <= self.dte_guard_threshold:
                    exit_price = current_spread_val
                    exit_flag = True
                    exit_reason = f"OPTION_DTE_EXPIRY_GUARD (DTE<={self.dte_guard_threshold})"
                # 2. 期权价差止盈：价差扩张达到目标 (+60%)
                elif current_spread_val >= pos.tp_price:
                    exit_price = pos.tp_price
                    exit_flag = True
                    exit_reason = f"OPTION_TAKE_PROFIT (+{int(self.option_tp_pct*100)}%)"
                # 3. 阶梯保本 / 移动止损 / 权利金兜底止损
                elif current_spread_val <= pos.sl_price:
                    exit_price = pos.sl_price
                    exit_flag = True
                    if pos.sl_price > pos.entry_price:
                        exit_reason = "OPTION_TRAILING_PROFIT (+15%)"
                    elif pos.sl_price >= pos.entry_price * 0.999:
                        exit_reason = "OPTION_BREAK_EVEN_PROTECTION (BE 0%)"
                    else:
                        exit_reason = f"OPTION_PREMIUM_SL (-{int(self.option_sl_pct*100)}%)"
                # 4. 正股锚定止损：正股收盘价跌破进场价的 -4% 支撑线
                elif close <= pos.entry_stock_price * (1.0 - self.stock_sl_pct):
                    exit_price = max(current_spread_val, pos.sl_price) if pos.sl_price >= pos.entry_price else current_spread_val
                    exit_flag = True
                    if pos.sl_price > pos.entry_price:
                        exit_reason = "OPTION_TRAILING_PROFIT (+15%)"
                    elif pos.sl_price >= pos.entry_price * 0.999:
                        exit_reason = "OPTION_BREAK_EVEN_PROTECTION (BE 0%)"
                    else:
                        exit_reason = f"OPTION_UNDERLYING_SL (-{int(self.stock_sl_pct*100)}% Stock)"

                if exit_flag:
                    self.cash += pos.qty * exit_price * 100
                    pnl = (exit_price - pos.entry_price) * pos.qty * 100
                    self.closed_trades.append({
                        "ticker": pos.ticker,
                        "asset_type": "OPTION",
                        "entry_date": pos.entry_date,
                        "exit_date": date_str,
                        "holding_days": pos.holding_days,
                        "entry_price": pos.entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": (exit_price - pos.entry_price) / (pos.entry_price + 1e-9),
                        "reason": exit_reason
                    })
                else:
                    remaining.append(pos)

        self.positions = remaining

    def _evaluate_current_portfolio(self, dt) -> float:
        total = 0.0
        for pos in self.positions:
            if pos.ticker not in self.market_data or dt not in self.market_data[pos.ticker].index:
                continue
            bar = self.market_data[pos.ticker].loc[dt]
            close = float(bar["close"])
            iv = max(0.20, float(bar.get("iv_proxy", 0.35)))

            if pos.asset_type == "EQUITY":
                total += pos.qty * close
            elif pos.asset_type == "OPTION":
                spread_val = self._calc_spread_price(
                    close, pos.strike, pos.strike_short, pos.remaining_dte, iv
                )
                total += pos.qty * spread_val * 100
        return total

    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        curve_df = pd.DataFrame(self.equity_curve)
        if not curve_df.empty:
            curve_df["returns"] = curve_df["equity"].pct_change().fillna(0)
            n_days = len(curve_df)
            total_return = (self.equity - self.initial_equity) / self.initial_equity
            cagr = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0.0

            curve_df["cummax"] = curve_df["equity"].cummax()
            curve_df["drawdown"] = (curve_df["equity"] - curve_df["cummax"]) / curve_df["cummax"]
            max_dd = float(curve_df["drawdown"].min())

            daily_rf = self.r / 252.0
            excess = curve_df["returns"] - daily_rf
            std = float(curve_df["returns"].std())
            sharpe = float(np.sqrt(252) * excess.mean() / (std + 1e-9))
            downside = curve_df["returns"][curve_df["returns"] < 0]
            downside_std = float(downside.std()) if not downside.empty else 1e-9
            sortino = float(np.sqrt(252) * excess.mean() / (downside_std + 1e-9))
        else:
            total_return, cagr, max_dd, sharpe, sortino = 0.0, 0.0, 0.0, 0.0, 0.0

        trades_df = pd.DataFrame(self.closed_trades)
        
        # 整体统计
        if not trades_df.empty:
            wins = trades_df[trades_df["pnl"] > 0]
            losses = trades_df[trades_df["pnl"] <= 0]
            win_rate = len(wins) / len(trades_df)
            avg_win = float(wins["pnl"].mean()) if not wins.empty else 0.0
            avg_loss = float(abs(losses["pnl"].mean())) if not losses.empty else 1.0
            pl_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0
        else:
            win_rate, pl_ratio, avg_win, avg_loss = 0.0, 0.0, 0.0, 0.0

        # 分品种独立统计函数
        def _calc_sub_stats(df_sub: pd.DataFrame) -> Dict[str, Any]:
            if df_sub.empty:
                return {
                    "trades": 0, "pnl": 0.0, "wins": 0, "losses": 0,
                    "win_rate": 0.0, "profit_loss_ratio": 0.0,
                    "avg_win": 0.0, "avg_loss": 0.0
                }
            sub_wins = df_sub[df_sub["pnl"] > 0]
            sub_losses = df_sub[df_sub["pnl"] <= 0]
            sub_wr = len(sub_wins) / len(df_sub)
            sub_avg_w = float(sub_wins["pnl"].mean()) if not sub_wins.empty else 0.0
            sub_avg_l = float(abs(sub_losses["pnl"].mean())) if not sub_losses.empty else 1.0
            sub_plr = sub_avg_w / sub_avg_l if sub_avg_l > 0 else 0.0
            return {
                "trades": len(df_sub),
                "pnl": float(df_sub["pnl"].sum()),
                "wins": len(sub_wins),
                "losses": len(sub_losses),
                "win_rate": sub_wr,
                "profit_loss_ratio": sub_plr,
                "avg_win": sub_avg_w,
                "avg_loss": sub_avg_l
            }

        stock_trades_df = trades_df[trades_df["asset_type"] == "EQUITY"] if not trades_df.empty else pd.DataFrame()
        option_trades_df = trades_df[trades_df["asset_type"] == "OPTION"] if not trades_df.empty else pd.DataFrame()

        stock_stats = _calc_sub_stats(stock_trades_df)
        option_stats = _calc_sub_stats(option_trades_df)

        dte_guard_trades = trades_df[trades_df["reason"].str.contains("DTE_EXPIRY_GUARD", na=False)] if not trades_df.empty else pd.DataFrame()
        dte_guard_count = len(dte_guard_trades)

        return {
            "initial_equity": self.initial_equity,
            "final_equity": round(self.equity, 2),
            "total_return": total_return,
            "cagr": cagr,
            "max_drawdown": max_dd,
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "win_rate": win_rate,
            "profit_loss_ratio": round(pl_ratio, 2),
            "total_trades": len(trades_df),
            "stock_trades_count": len(stock_trades_df),
            "option_trades_count": len(option_trades_df),
            "dte_guard_count": dte_guard_count,
            "stock_stats": stock_stats,
            "option_stats": option_stats,
            "curve_df": curve_df,
            "trades_df": trades_df
        }
