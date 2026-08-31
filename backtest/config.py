# backtest/config.py
from dataclasses import dataclass

@dataclass
class BacktestConfig:
    start_date: str = "2023-01-01"
    end_date: str = "2026-06-30"
    initial_equity: float = 100000.0   # 初始本金 $100k
    commission_rate: float = 0.0001    # Alpaca 计入 SEC/FINRA 规费
    slippage_bps: float = 5.0          # 滑点 5 个基点 (0.05%)
    enable_llm_cache: bool = True      # 开启大模型离线缓存
    benchmark_ticker: str = "SPY"