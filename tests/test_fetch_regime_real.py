"""Integration test module for real-time VIX and FRED credit spread data fetching."""

import pytest
import yfinance as yf
from core.regime_engine import RegimeEngine, RegimeState


def test_fetch_regime_real_vix_details():
    """测试实际调用 yfinance 拉取 VIX 详细数据及 RegimeEngine 状态输出"""
    # 1. 直接拉取并打印 yfinance 5日 VIX 详细行情数据
    vix_ticker = yf.Ticker("^VIX")
    vix_hist = vix_ticker.history(period="5d")

    print("\n" + "=" * 60)
    print("【yfinance ^VIX 5日近况行情数据详情】")
    print("=" * 60)
    print(vix_hist[["Open", "High", "Low", "Close", "Volume"]])
    print("=" * 60)

    # 断言行情数据不为空且包含关键列
    assert not vix_hist.empty, "拉取的 VIX 历史数据不应为空"
    assert "Close" in vix_hist.columns, "数据表中需包含 Close 列"

    latest_close = float(vix_hist["Close"].iloc[-1])
    latest_date = str(vix_hist.index[-1].strftime("%Y-%m-%d"))

    print(f"最新交易日 ({latest_date}) VIX 收盘价: {latest_close:.2f}")

    # 2. 调用 RegimeEngine 计算最终市场环境状态
    engine = RegimeEngine(vix_threshold=20.0, hy_spread_threshold=10.0)
    state: RegimeState = engine.fetch_regime()

    print("\n" + "=" * 60)
    print("【RegimeEngine 计算结果状态详情】")
    print("=" * 60)
    print(f"VIX 指数值      : {state.vix:.2f}")
    print(f"高收益债利差    : {state.hy_spread:.2f}%")
    print(
        f"是否开启避险    : {state.is_risk_off} "
        f"({'Risk-Off 规避风险' if state.is_risk_off else 'Risk-On 风险偏好'})"
    )
    print(f"动量策略权重    : {state.momentum_weight:.2f}")
    print(f"宏观策略权重    : {state.macro_weight:.2f}")
    print(f"逆向策略权重    : {state.contrarian_weight:.2f}")
    print("=" * 60)

    # 3. 详细断言校验
    assert isinstance(state, RegimeState)
    assert state.vix == pytest.approx(latest_close, abs=1e-4)
    assert isinstance(state.is_risk_off, bool)
    assert 0.0 <= state.momentum_weight <= 1.0
    assert 0.0 <= state.macro_weight <= 1.0
    assert 0.0 <= state.contrarian_weight <= 1.0
    total_weights = (
        state.momentum_weight + state.macro_weight + state.contrarian_weight
    )
    assert total_weights == pytest.approx(1.0)
