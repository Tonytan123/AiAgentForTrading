"""Unit and integration test module for RegimeEngine."""

from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from core.regime_engine import RegimeEngine, RegimeState


def test_fetch_regime_real_api():
    """测试实际调用 yfinance 拉取 VIX 数据 (集成测试)"""
    engine = RegimeEngine()
    state = engine.fetch_regime()

    assert isinstance(state, RegimeState)
    assert isinstance(state.vix, float)
    assert state.vix > 0, "VIX 值应当大于 0"
    assert isinstance(state.is_risk_off, bool)
    total_weights = (
        state.momentum_weight + state.macro_weight + state.contrarian_weight
    )
    assert total_weights == pytest.approx(1.0)


def test_fetch_regime_mocked_normal_vix():
    """使用 Mock 模拟正常 VIX 数据 (VIX < Threshold, 风险偏好/Risk-On)"""
    mock_df = pd.DataFrame({"Close": [15.2, 14.8, 15.0]})

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_df
        mock_ticker_cls.return_value = mock_ticker_instance

        engine = RegimeEngine(vix_threshold=20.0, hy_spread_threshold=10.0)
        state = engine.fetch_regime()

        mock_ticker_cls.assert_called_once_with("^VIX")
        assert state.vix == 15.0
        assert state.is_risk_off is False
        assert state.momentum_weight == 0.5


def test_fetch_regime_mocked_high_vix():
    """使用 Mock 模拟高 VIX 数据 (VIX > Threshold, 规避风险/Risk-Off)"""
    mock_df = pd.DataFrame({"Close": [22.0, 25.4, 28.1]})

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_df
        mock_ticker_cls.return_value = mock_ticker_instance

        engine = RegimeEngine(vix_threshold=20.0, hy_spread_threshold=10.0)
        state = engine.fetch_regime()

        assert state.vix == 28.1
        assert state.is_risk_off is True
        assert state.macro_weight == 0.5


def test_fetch_regime_mocked_empty_history():
    """使用 Mock 模拟 yfinance 返回空数据 (触发默认兜底值 16.5)"""
    mock_df = pd.DataFrame()

    with patch("yfinance.Ticker") as mock_ticker_cls:
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_df
        mock_ticker_cls.return_value = mock_ticker_instance

        engine = RegimeEngine()
        state = engine.fetch_regime()

        assert state.vix == 16.5
        assert state.is_risk_off is False
