# run_backtest.py
import yfinance as yf
import pandas as pd
from backtest.config import BacktestConfig
from backtest.backtest_engine import QuantBacktester

def load_real_market_data(tickers, start_date, end_date):
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
        df["days_to_earnings"] = 30
        data[t] = df.dropna()
    return data

def load_macro_data(start_date, end_date):
    vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    if isinstance(vix.columns, pd.MultiIndex):
        vix.columns = vix.columns.get_level_values(0)
    
    macro_df = pd.DataFrame(index=vix.index)
    macro_df["VIX"] = vix["Close"]
    macro_df["HY_SPREAD"] = 3.8
    return macro_df.dropna()

if __name__ == "__main__":
    cfg = BacktestConfig(start_date="2024-01-01", end_date="2026-06-01")
    tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA"]
    
    print("[*] 正在拉取历史行情与宏观指标...")
    market_data = load_real_market_data(tickers, cfg.start_date, cfg.end_date)
    macro_data = load_macro_data(cfg.start_date, cfg.end_date)

    print("[*] 启动量化多智能体回测引擎...")
    tester = QuantBacktester(cfg, market_data, macro_data)
    results = tester.run()

    print("\n" + "=" * 35 + " 回测绩效评估报告 " + "=" * 35)
    print(f"初始本金:          ${results['initial_equity']:,.2f}")
    print(f"期末资产净值:      ${results['final_equity']:,.2f}")
    print(f"累计总收益率:      {results['total_return']}")
    print(f"年化复合收益 (CAGR):{results['cagr']}")
    print(f"最大历史回撤 (MDD): {results['max_drawdown']}")
    print(f"夏普比率 (Sharpe): {results['sharpe_ratio']}")
    print(f"索提诺比率(Sortino):{results['sortino_ratio']}")
    print(f"交易胜率 (WinRate):{results['win_rate']}")
    print(f"盈亏比 (P/L Ratio):{results['profit_loss_ratio']}")
    print(f"总成交笔数:        {results['total_trades']}")
    print("=" * 86)