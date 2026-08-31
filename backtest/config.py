# backtest/config.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class BacktestConfig:
    start_date: str = "2025-08-01"
    end_date: str = "2026-08-31"
    initial_equity: float = 100000.0   # 初始本金 $100k
    commission_rate: float = 0.0001    # Alpaca 计入 SEC/FINRA 规费
    slippage_bps: float = 5.0          # 滑点 5 个基点 (0.05%)
    enable_llm_cache: bool = True      # 开启大模型离线缓存
    benchmark_ticker: str = "SPY"
    risk_free_rate: float = 0.045      # 无风险利率 4.5%
    stock_budget_pct: float = 0.08     # 正股单仓上限 8.0% (原 4.8%)
    option_budget_pct: float = 0.015   # 期权单笔权利金上限 1.5%
    stock_tp_pct: float = 0.08         # 正股止盈 +8%
    stock_sl_pct: float = 0.04         # 正股止损 -4%
    option_tp_pct: float = 0.50        # 期权止盈 +50%
    option_sl_pct: float = 0.50        # 期权止损 -50%
    option_dte: int = 28               # 期权开仓 DTE
    dte_guard_threshold: int = 3       # 期权到期守护阈值 DTE <= 3
    stock_timeout_days: int = 28       # 正股超时平仓天数
    cash_sweep_enabled: bool = True    # 开启闲置资金自动买入国债/货币基金 (SGOV)
    cash_sweep_symbol: str = "SGOV"    # 国债/货基 ETF 标的代码
    cash_sweep_yield: float = 0.045    # 国债/货基年化无风险收益率 4.5%