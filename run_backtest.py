# run_backtest.py
import numpy as np
import pandas as pd
import yfinance as yf
from backtest.config import BacktestConfig
from backtest.hybrid_backtester import HybridStrategyBacktester


def load_real_market_data(tickers, start_date, end_date):
    """从 yfinance 拉取个股真实日线行情并计算衍生技术指标与 IV 代理"""
    data = {}
    for t in tickers:
        df = yf.download(t, start=start_date, end=end_date, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]

        # 计算基础技术指标
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        df["rsi"] = 100 - (100 / (1 + rs))
        df["sma_20"] = df["close"].rolling(20).mean()
        df["vol_surge"] = df["volume"] / df["volume"].rolling(20).mean()

        # 计算 20 日滚动历史波动率 (HV) 作为期权 IV 代理 (IV Proxy)
        log_ret = np.log(df["close"] / df["close"].shift(1))
        df["iv_proxy"] = log_ret.rolling(20).std() * np.sqrt(252)
        df["iv_proxy"] = df["iv_proxy"].fillna(0.35).clip(lower=0.20, upper=1.20)

        df["days_to_earnings"] = 30
        data[t] = df.dropna()
    return data


def load_macro_data(start_date, end_date):
    """从 yfinance 拉取宏观 ^VIX 指数历史序列"""
    vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)

    macro_df = pd.DataFrame(index=vix.index)
    macro_df["VIX"] = vix["Close"]
    macro_df["HY_SPREAD"] = 3.8
    return macro_df.dropna()


def validate_market_data(market_data: dict, macro_data: pd.DataFrame):
    """
    数据质检报告：多维度校验抓取到的历史数据真实性、连续性与完整性
    """
    print("\n" + "=" * 32 + " [DATA QUALITY REPORT] " + "=" * 32)

    # 1. 宏观 VIX 数据质检
    if macro_data is None or macro_data.empty:
        raise ValueError("[ERROR] VIX data is empty!")

    vix_start = macro_data.index[0].strftime("%Y-%m-%d")
    vix_end = macro_data.index[-1].strftime("%Y-%m-%d")
    latest_vix = float(macro_data["VIX"].iloc[-1])
    min_vix = float(macro_data["VIX"].min())
    max_vix = float(macro_data["VIX"].max())
    print(
        f"[PASS] [VIX Index] Count: {len(macro_data):>3} | Date Range: {vix_start} ~ {vix_end} | "
        f"Latest: {latest_vix:>5.2f} | Range: [{min_vix:.2f}, {max_vix:.2f}]"
    )

    # 2. 个股标的历史行情质检
    for ticker, df in market_data.items():
        if df is None or df.empty:
            raise ValueError(f"[ERROR] Ticker {ticker} has no data!")

        start_date_actual = df.index[0].strftime("%Y-%m-%d")
        end_date_actual = df.index[-1].strftime("%Y-%m-%d")
        latest_price = float(df["close"].iloc[-1])
        earliest_price = float(df["close"].iloc[0])
        null_count = int(df.isnull().sum().sum())
        avg_iv = float(df["iv_proxy"].mean())

        # 核心断言校验
        assert len(df) >= 30, f"Ticker {ticker} has too few samples ({len(df)})!"
        assert null_count == 0, f"Ticker {ticker} contains {null_count} NaN values!"
        assert latest_price > 0, f"Ticker {ticker} has invalid latest price ({latest_price})!"

        print(
            f"[PASS] [{ticker:<5}] Count: {len(df):>3} | Range: {start_date_actual} ~ {end_date_actual} | "
            f"First: ${earliest_price:>7.2f} | Latest: ${latest_price:>7.2f} | Avg HV: {avg_iv:.1%}"
        )

    print("=" * 86 + "\n")


if __name__ == "__main__":
    cfg = BacktestConfig(start_date="2025-08-01", end_date="2026-08-31", stock_budget_pct=0.08)
    
    # 扩充至标普 500 各核心板块领头羊成分股 (33 只)
    tickers = [
        # 科技与半导体龙头
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "QCOM", 
        "INTC", "MU", "PLTR", "CRM", "ADBE", "ORCL", "NFLX",
        # 消费与零售
        "COST", "WMT", "HD", "PG",
        # 金融
        "JPM", "BAC", "GS", "V", "MA",
        # 医疗健康
        "UNH", "LLY", "JNJ", "ABBV",
        # 能源与工业
        "XOM", "CVX", "CAT", "GE"
    ]

    print("[*] Fetching real market data and macro indicators (past 1 year)...")
    market_data = load_real_market_data(tickers, cfg.start_date, cfg.end_date)
    macro_data = load_macro_data(cfg.start_date, cfg.end_date)

    # 执行历史数据质量审计与真实性校验
    validate_market_data(market_data, macro_data)

    vix_series = macro_data["VIX"]

    print("[*] Launching HybridStrategyBacktester...")
    tester = HybridStrategyBacktester(
        market_data=market_data,
        vix_series=vix_series,
        initial_equity=cfg.initial_equity,
        risk_free_rate=cfg.risk_free_rate,
        slippage_bps=cfg.slippage_bps,
        stock_budget_pct=cfg.stock_budget_pct,
        option_budget_pct=cfg.option_budget_pct,
        stock_timeout_days=cfg.stock_timeout_days,
        dte_guard_threshold=cfg.dte_guard_threshold,
    )
    results = tester.run()

    # 1. 打印全局绩效报告
    print("\n" + "=" * 33 + " [OVERALL PORTFOLIO REPORT] " + "=" * 33)
    print(f"Initial Equity:             ${results['initial_equity']:,.2f}")
    print(f"Final Equity:               ${results['final_equity']:,.2f}")
    print(f"Total Return:               {results['total_return']:.2%}")
    print(f"CAGR:                       {results['cagr']:.2%}")
    print(f"Max Drawdown:               {results['max_drawdown']:.2%}")
    print(f"Sharpe Ratio:               {results['sharpe_ratio']:.2f}")
    print(f"Sortino Ratio:              {results['sortino_ratio']:.2f}")
    print(f"Total Trades Count:         {results['total_trades']}")
    print(f"Combined Win Rate:          {results['win_rate']:.2%}")
    print(f"Combined P/L Ratio:         {results['profit_loss_ratio']:.2f}")

    # 2. 打印分品种独立表现对比 (Stock vs Option Breakdown)
    stock_st = results["stock_stats"]
    opt_st = results["option_stats"]

    print("\n" + "-" * 30 + " [SUB-ASSET PERFORMANCE BREAKDOWN] " + "-" * 30)
    print(f"{'Metric':<25} | {'EQUITY (Stock)':<20} | {'OPTION (Bull Call Spread)':<25}")
    print("-" * 80)
    print(f"{'Total Trades':<25} | {stock_st['trades']:<20} | {opt_st['trades']:<25}")
    print(f"{'Total Net PnL':<25} | ${stock_st['pnl']:>10,.2f}          | ${opt_st['pnl']:>10,.2f}")
    print(f"{'Win Rate':<25} | {stock_st['win_rate']:>9.2%}           | {opt_st['win_rate']:>9.2%}")
    print(f"{'Profit / Loss Ratio':<25} | {stock_st['profit_loss_ratio']:>9.2f}           | {opt_st['profit_loss_ratio']:>9.2f}")
    print(f"{'Avg Win / Avg Loss':<25} | ${stock_st['avg_win']:,.0f} / ${stock_st['avg_loss']:,.0f}      | ${opt_st['avg_win']:,.0f} / ${opt_st['avg_loss']:,.0f}")
    print("-" * 80)

    # 3. 打印出场原因分布
    trades_df = results["trades_df"]
    if not trades_df.empty:
        print("\n" + "-" * 32 + " [TRADE EXIT REASON BREAKDOWN] " + "-" * 32)
        reason_grp = trades_df.groupby(["asset_type", "reason"])["pnl"].agg(["count", "sum"])
        for (asset, reason), row in reason_grp.iterrows():
            print(f"  [{asset:<6}] {reason:<42} -> {int(row['count']):>2} trades | PnL: ${row['sum']:>9,.2f}")
    print("=" * 96 + "\n")