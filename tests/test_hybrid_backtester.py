"""
tests/test_hybrid_backtester.py
正股与期权双轨量化策略回测引擎完整单元测试与集成测试
"""

import math
import numpy as np
import pandas as pd
import pytest

from backtest.hybrid_backtester import (
    HybridPosition,
    HybridStrategyBacktester,
    black_scholes_price,
)


@pytest.fixture
def sample_hybrid_backtester():
    """创建一个带有基础测试环境的 HybridStrategyBacktester 实例"""
    dates = pd.date_range(start="2025-08-01", periods=60, freq="B")
    vix_series = pd.Series(16.5, index=dates)

    # 构造基础股票行情
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 120, len(dates)),
            "high": np.linspace(102, 122, len(dates)),
            "low": np.linspace(99, 119, len(dates)),
            "close": np.linspace(101, 121, len(dates)),
            "volume": [1000000] * len(dates),
            "rsi": [65.0] * len(dates),
            "sma_20": np.linspace(98, 118, len(dates)),
            "vol_surge": [1.5] * len(dates),
            "iv_proxy": [0.30] * len(dates),
            "days_to_earnings": [45] * len(dates),
        },
        index=dates,
    )

    market_data = {"AAPL": df}
    return HybridStrategyBacktester(
        market_data=market_data,
        vix_series=vix_series,
        initial_equity=100000.0,
        risk_free_rate=0.045,
        dte_guard_threshold=4,
        option_sl_pct=0.40,
        option_tp_pct=0.50
    )


def test_hybrid_position_initialization():
    """测试 HybridPosition 持仓对象正确初始化及时间戳解析"""
    pos_equity = HybridPosition(
        asset_type="EQUITY",
        ticker="NVDA",
        entry_date="2025-08-01",
        qty=40,
        entry_price=120.0,
        tp_price=129.6,
        sl_price=115.2,
    )
    assert pos_equity.asset_type == "EQUITY"
    assert pos_equity.ticker == "NVDA"
    assert pos_equity.qty == 40
    assert pos_equity.holding_days == 0
    assert pos_equity.remaining_dte == 0
    assert pos_equity.entry_dt == pd.Timestamp("2025-08-01")

    pos_option = HybridPosition(
        asset_type="OPTION",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=2,
        entry_price=5.0,
        tp_price=7.5,
        sl_price=3.0,
        option_type="Call",
        strike=102.0,
        initial_dte=28,
        iv=0.35,
    )
    assert pos_option.asset_type == "OPTION"
    assert pos_option.remaining_dte == 28
    assert pos_option.expiry_dt == pd.Timestamp("2025-08-29")
    assert pos_option.iv == 0.35
    assert pos_option.strike == 102.0


def test_equity_settlement_take_profit(sample_hybrid_backtester):
    """测试正股达到止盈价 (+8%) 成功撮合出场"""
    tester = sample_hybrid_backtester
    pos = HybridPosition(
        asset_type="EQUITY",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=50,
        entry_price=100.0,
        tp_price=108.0,
        sl_price=96.0,
    )
    tester.positions.append(pos)
    initial_cash = tester.cash

    dt = tester.vix_series.index[0]
    tester.market_data["AAPL"].loc[dt, "high"] = 110.0
    tester.market_data["AAPL"].loc[dt, "low"] = 101.0
    tester.market_data["AAPL"].loc[dt, "close"] = 109.0

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert trade["asset_type"] == "EQUITY"
    assert trade["exit_price"] == 108.0
    assert trade["pnl"] == (108.0 - 100.0) * 50
    assert trade["reason"] == "STOCK_TAKE_PROFIT (+8%)"
    assert tester.cash == initial_cash + 50 * 108.0


def test_equity_settlement_stop_loss(sample_hybrid_backtester):
    """测试正股达到止损价 (-4%) 成功撮合出场"""
    tester = sample_hybrid_backtester
    pos = HybridPosition(
        asset_type="EQUITY",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=50,
        entry_price=100.0,
        tp_price=108.0,
        sl_price=96.0,
    )
    tester.positions.append(pos)
    initial_cash = tester.cash

    dt = tester.vix_series.index[0]
    tester.market_data["AAPL"].loc[dt, "high"] = 99.0
    tester.market_data["AAPL"].loc[dt, "low"] = 95.0
    tester.market_data["AAPL"].loc[dt, "close"] = 95.5

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert trade["exit_price"] == 96.0
    assert trade["pnl"] == (96.0 - 100.0) * 50
    assert trade["reason"] == "STOCK_STOP_LOSS (-4%)"
    assert tester.cash == initial_cash + 50 * 96.0


def test_equity_settlement_timeout_28d(sample_hybrid_backtester):
    """测试正股持仓达到 28 天超时强制平仓"""
    tester = sample_hybrid_backtester
    pos = HybridPosition(
        asset_type="EQUITY",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=50,
        entry_price=100.0,
        tp_price=108.0,
        sl_price=96.0,
    )
    pos.holding_days = 27
    tester.positions.append(pos)

    dt = tester.vix_series.index[0]
    tester.market_data["AAPL"].loc[dt, "high"] = 104.0
    tester.market_data["AAPL"].loc[dt, "low"] = 101.0
    tester.market_data["AAPL"].loc[dt, "close"] = 103.0

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert trade["exit_price"] == 103.0
    assert trade["reason"] == "STOCK_TIMEOUT_28D"


def test_option_settlement_take_profit(sample_hybrid_backtester):
    """测试期权价值上涨达到 +50% 触发止盈出场"""
    tester = sample_hybrid_backtester
    premium = 5.0
    pos = HybridPosition(
        asset_type="OPTION",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=2,
        entry_price=premium,
        tp_price=7.50,
        sl_price=3.00,
        option_type="Call",
        strike=102.0,
        initial_dte=25,
        iv=0.35,
    )
    tester.positions.append(pos)
    initial_cash = tester.cash

    dt = tester.vix_series.index[0]
    tester.market_data["AAPL"].loc[dt, "close"] = 130.0
    tester.market_data["AAPL"].loc[dt, "high"] = 131.0
    tester.market_data["AAPL"].loc[dt, "low"] = 129.0

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert trade["asset_type"] == "OPTION"
    assert trade["exit_price"] == 7.50
    assert trade["pnl"] == (7.50 - 5.0) * 2 * 100
    assert "OPTION_TAKE_PROFIT" in trade["reason"]
    assert tester.cash == initial_cash + 2 * 7.50 * 100


def test_option_settlement_stop_loss(sample_hybrid_backtester):
    """测试期权价值下跌达到止损线触发止损出场"""
    tester = sample_hybrid_backtester
    premium = 5.0
    pos = HybridPosition(
        asset_type="OPTION",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=2,
        entry_price=premium,
        tp_price=7.50,
        sl_price=3.00,
        option_type="Call",
        strike=102.0,
        initial_dte=20,
        iv=0.35,
    )
    tester.positions.append(pos)

    dt = tester.vix_series.index[0]
    tester.market_data["AAPL"].loc[dt, "close"] = 75.0
    tester.market_data["AAPL"].loc[dt, "high"] = 78.0
    tester.market_data["AAPL"].loc[dt, "low"] = 74.0

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert trade["exit_price"] == 3.00
    assert trade["pnl"] == (3.00 - 5.0) * 2 * 100
    assert "OPTION_PREMIUM_SL" in trade["reason"] or "OPTION_STOP_LOSS" in trade["reason"]


def test_option_dte_expiry_guard(sample_hybrid_backtester):
    """测试期权 DTE 临期优先触发 Sentinel 守护清仓机制"""
    tester = sample_hybrid_backtester
    dt = tester.vix_series.index[0]
    # 设置 expiry_dt 仅距当前日期 2 天 (自然日 DTE=2 <= threshold 4)
    pos = HybridPosition(
        asset_type="OPTION",
        ticker="AAPL",
        entry_date="2025-08-01",
        qty=1,
        entry_price=4.0,
        tp_price=10.0,
        sl_price=1.0,
        option_type="Call",
        strike=102.0,
        initial_dte=2,
        iv=0.30,
        entry_dt=dt,
        expiry_dt=dt + pd.Timedelta(days=2)
    )
    tester.positions.append(pos)

    tester.market_data["AAPL"].loc[dt, "close"] = 104.0

    tester._process_daily_settlement(dt, "2025-08-01")

    assert len(tester.positions) == 0
    assert len(tester.closed_trades) == 1
    trade = tester.closed_trades[0]
    assert "DTE_EXPIRY_GUARD" in trade["reason"]


def test_regime_weights_and_signal_routing():
    """测试宏观环境调权与双轨交易信号路由"""
    dates = pd.date_range("2025-08-01", periods=2, freq="B")
    
    # 1. RISK-ON 环境 (VIX=15.0) + 强动量信号 -> 触发期权 Long Call
    vix_risk_on = pd.Series([15.0, 15.0], index=dates)
    df_strong = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "rsi": [65.0, 65.0],
            "sma_20": [95.0, 95.0],
            "vol_surge": [1.5, 1.5],
            "iv_proxy": [0.30, 0.30],
            "days_to_earnings": [30, 30],
        },
        index=dates,
    )
    tester_opt = HybridStrategyBacktester(
        market_data={"NVDA": df_strong},
        vix_series=vix_risk_on,
        initial_equity=100000.0,
    )
    res_opt = tester_opt.run()
    assert len(tester_opt.positions) == 1
    assert tester_opt.positions[0].asset_type == "OPTION"
    assert tester_opt.positions[0].option_type in ["BullCallSpread", "Call"]
    assert tester_opt.positions[0].strike in [100.0, 101.0, 102.0]

    # 2. RISK-ON 环境 + 较温和 RSI -> 触发正股 Bracket OCO
    df_stock = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "rsi": [52.0, 52.0],
            "sma_20": [95.0, 95.0],
            "vol_surge": [1.5, 1.5],
            "iv_proxy": [0.30, 0.30],
            "days_to_earnings": [30, 30],
        },
        index=dates,
    )
    tester_stock = HybridStrategyBacktester(
        market_data={"AAPL": df_stock},
        vix_series=vix_risk_on,
        initial_equity=100000.0,
    )
    res_stock = tester_stock.run()
    assert len(tester_stock.positions) == 1
    assert tester_stock.positions[0].asset_type == "EQUITY"
    assert tester_stock.positions[0].tp_price == 108.0
    assert tester_stock.positions[0].sl_price == 96.0


def test_hard_risk_budget_limits():
    """测试硬风控预算约束 (期权权利金 <= 1.5%, 正股单仓 <= 4.8%)"""
    dates = pd.date_range("2025-08-01", periods=2, freq="B")
    vix = pd.Series([15.0, 15.0], index=dates)

    # 1. 期权预算测试
    df_opt = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "rsi": [65.0, 65.0],
            "sma_20": [90.0, 90.0],
            "vol_surge": [1.5, 1.5],
            "iv_proxy": [0.30, 0.30],
            "days_to_earnings": [30, 30],
        },
        index=dates,
    )
    tester = HybridStrategyBacktester(
        market_data={"TSLA": df_opt},
        vix_series=vix,
        initial_equity=100000.0,
        option_budget_pct=0.015,
    )
    tester.run()
    opt_pos = [p for p in tester.positions if p.asset_type == "OPTION"]
    assert len(opt_pos) == 1
    total_opt_cost = opt_pos[0].qty * opt_pos[0].entry_price * 100
    assert total_opt_cost <= 100000.0 * 0.015 or opt_pos[0].qty == 1

    # 2. 正股预算测试
    df_eq = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "high": [101.0, 101.0],
            "low": [99.0, 99.0],
            "rsi": [52.0, 52.0],
            "sma_20": [90.0, 90.0],
            "vol_surge": [1.5, 1.5],
            "iv_proxy": [0.30, 0.30],
            "days_to_earnings": [30, 30],
        },
        index=dates,
    )
    tester_eq = HybridStrategyBacktester(
        market_data={"MSFT": df_eq},
        vix_series=vix,
        initial_equity=100000.0,
        stock_budget_pct=0.048,
    )
    tester_eq.run()
    eq_pos = [p for p in tester_eq.positions if p.asset_type == "EQUITY"]
    assert len(eq_pos) == 1
    total_eq_val = eq_pos[0].qty * eq_pos[0].entry_price
    assert total_eq_val <= 100000.0 * 0.048


def test_performance_metrics_and_sub_asset_breakdown():
    """测试 KPI 指标与分品种独立统计数据结构的完整性"""
    np.random.seed(42)
    n_days = 252
    dates = pd.date_range("2025-08-01", periods=n_days, freq="B")
    
    vix = pd.Series(18.0 + np.sin(np.linspace(0, 10, n_days)) * 3.0, index=dates)

    price_series = 100.0 * np.cumprod(1 + np.random.normal(0.0008, 0.012, n_days))
    df = pd.DataFrame(
        {
            "close": price_series,
            "high": price_series * 1.01,
            "low": price_series * 0.99,
            "volume": [1000000] * n_days,
            "rsi": 50 + np.random.normal(5, 10, n_days),
            "sma_20": pd.Series(price_series).rolling(20, min_periods=1).mean().values,
            "vol_surge": [1.4] * n_days,
            "iv_proxy": [0.32] * n_days,
            "days_to_earnings": [30] * n_days,
        },
        index=dates,
    )

    tester = HybridStrategyBacktester(
        market_data={"META": df},
        vix_series=vix,
        initial_equity=100000.0,
    )
    metrics = tester.run()

    # 验证分品种独立统计存在且包含必需字段
    assert "stock_stats" in metrics
    assert "option_stats" in metrics
    for stats in [metrics["stock_stats"], metrics["option_stats"]]:
        for k in ["trades", "pnl", "wins", "losses", "win_rate", "profit_loss_ratio", "avg_win", "avg_loss"]:
            assert k in stats

    curve_df = metrics["curve_df"]
    assert isinstance(curve_df, pd.DataFrame)
    assert len(curve_df) == n_days
    assert "equity" in curve_df.columns
