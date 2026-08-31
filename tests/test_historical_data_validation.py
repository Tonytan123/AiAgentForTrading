"""
tests/test_historical_data_validation.py
真实历史行情与宏观数据抓取及质检自动化测试用例
"""

import numpy as np
import pandas as pd
import pytest
from run_backtest import load_real_market_data, load_macro_data, validate_market_data


def test_real_historical_market_data_fetching_and_validation():
    """
    测试通过 yfinance 真实拉取标的历史 K 线与衍生指标，并进行多维度数据质量校验
    """
    tickers = ["AAPL", "NVDA"]
    start_date = "2025-08-01"
    end_date = "2026-08-31"

    print("\n" + "=" * 60)
    print("[TEST] Fetching and validating real historical market data...")
    print("=" * 60)

    # 1. 执行数据抓取
    market_data = load_real_market_data(tickers, start_date, end_date)
    assert len(market_data) == len(tickers), f"应成功拉取 {len(tickers)} 个标的数据"

    for ticker in tickers:
        df = market_data[ticker]
        assert not df.empty, f"标的 {ticker} 历史数据不应为空"
        
        # 字段完整性校验
        required_cols = ["open", "high", "low", "close", "volume", "rsi", "sma_20", "vol_surge", "iv_proxy"]
        for col in required_cols:
            assert col in df.columns, f"数据表中缺少必要字段: {col}"

        # 样本量校验 (近一年交易日通常 >= 100 天)
        assert len(df) >= 50, f"标的 {ticker} 数据样本量偏少 ({len(df)} 条)"

        # 无缺失值校验
        assert df.isnull().sum().sum() == 0, f"标的 {ticker} 数据中存在 NaN 空值"

        # 价格与技术指标合理性校验
        assert (df["close"] > 0).all(), f"标的 {ticker} 存在非正收盘价"
        assert (df["high"] >= df["low"]).all(), f"标的 {ticker} 存在 high < low 异常"
        assert (df["rsi"].between(0, 100)).all(), f"标的 {ticker} RSI 值超出 [0, 100] 范围"
        assert (df["iv_proxy"] > 0).all(), f"标的 {ticker} 历史波动率代理异常"

        first_date = df.index[0].strftime("%Y-%m-%d")
        last_date = df.index[-1].strftime("%Y-%m-%d")
        first_close = float(df["close"].iloc[0])
        last_close = float(df["close"].iloc[-1])
        avg_iv = float(df["iv_proxy"].mean())

        print(f"[PASS] [{ticker}] Samples: {len(df)} | Range: {first_date} ~ {last_date}")
        print(f"       First Close: ${first_close:,.2f} | Latest Close: ${last_close:,.2f} | Avg HV: {avg_iv:.2%}")


def test_real_macro_vix_data_fetching_and_validation():
    """
    测试真实拉取宏观 ^VIX 指数序列并验证其连续性与合理性
    """
    start_date = "2025-08-01"
    end_date = "2026-08-31"

    print("\n" + "=" * 60)
    print("[TEST] Fetching and validating macro VIX data...")
    print("=" * 60)

    macro_df = load_macro_data(start_date, end_date)
    assert not macro_df.empty, "宏观数据不应为空"
    assert "VIX" in macro_df.columns, "宏观数据必须包含 VIX 列"
    assert "HY_SPREAD" in macro_df.columns, "宏观数据必须包含 HY_SPREAD 列"

    vix_series = macro_df["VIX"]
    assert len(vix_series) >= 50, f"VIX 数据点偏少 ({len(vix_series)} 条)"
    assert (vix_series > 5.0).all() and (vix_series < 100.0).all(), "VIX 数值超出正常范围 (5 ~ 100)"

    latest_vix = float(vix_series.iloc[-1])
    min_vix = float(vix_series.min())
    max_vix = float(vix_series.max())
    print(f"[PASS] [^VIX] Samples: {len(vix_series)} | Latest: {latest_vix:.2f} | Range: [{min_vix:.2f}, {max_vix:.2f}]")


def test_validate_market_data_quality_reporter():
    """
    测试数据质检报告输出函数 validate_market_data 的执行与异常拦截
    """
    dates = pd.date_range("2025-08-01", periods=60, freq="B")
    mock_df = pd.DataFrame(
        {
            "open": [150.0] * 60,
            "high": [155.0] * 60,
            "low": [148.0] * 60,
            "close": [152.0] * 60,
            "volume": [1000000] * 60,
            "rsi": [55.0] * 60,
            "sma_20": [150.0] * 60,
            "vol_surge": [1.1] * 60,
            "iv_proxy": [0.28] * 60,
        },
        index=dates,
    )
    mock_macro = pd.DataFrame({"VIX": [17.5] * 60, "HY_SPREAD": [3.8] * 60}, index=dates)

    # 正常数据通过质检
    validate_market_data({"AAPL": mock_df}, mock_macro)

    # 异常数据触发拦截
    empty_macro = pd.DataFrame()
    with pytest.raises(ValueError, match="VIX data is empty"):
        validate_market_data({"AAPL": mock_df}, empty_macro)
