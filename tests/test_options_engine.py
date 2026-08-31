"""
tests/test_options_engine.py
期权定价引擎与希腊字母计算单元测试
"""

import math
import pytest
from core.options_engine import black_scholes_price, calculate_greeks, OptionsEngine


def test_black_scholes_call_atm():
    """测试平值 (ATM) 看涨期权定价"""
    s = 100.0
    k = 100.0
    t_days = 30
    r = 0.045
    sigma = 0.30

    price = black_scholes_price(s, k, t_days, r, sigma, "call")
    assert price > 0.0
    # 理论价格应该在 3.0 ~ 4.5 之间
    assert 2.5 <= price <= 5.0


def test_black_scholes_put_atm():
    """测试平值 (ATM) 看跌期权定价"""
    s = 100.0
    k = 100.0
    t_days = 30
    r = 0.045
    sigma = 0.30

    price = black_scholes_price(s, k, t_days, r, sigma, "put")
    assert price > 0.0
    assert 2.0 <= price <= 4.5


def test_black_scholes_call_put_parity():
    """测试看涨看跌平价公式 (Put-Call Parity: C - P = S - K * e^(-rT))"""
    s = 150.0
    k = 145.0
    t_days = 60
    r = 0.05
    sigma = 0.25
    t = t_days / 365.0

    call_price = black_scholes_price(s, k, t_days, r, sigma, "call")
    put_price = black_scholes_price(s, k, t_days, r, sigma, "put")

    lhs = call_price - put_price
    rhs = s - k * math.exp(-r * t)
    assert pytest.approx(lhs, abs=0.05) == rhs


def test_black_scholes_expiration_boundary():
    """测试到期日边界 (DTE <= 0) 时返回内在价值"""
    s = 120.0
    k = 100.0
    # 到期且 ITM
    call_itm = black_scholes_price(s, k, 0, 0.045, 0.30, "call")
    assert call_itm == 20.0

    # 到期且 OTM
    call_otm = black_scholes_price(90.0, 100.0, 0, 0.045, 0.30, "call")
    assert call_otm == 0.0

    # Put 到期且 ITM
    put_itm = black_scholes_price(80.0, 100.0, -1, 0.045, 0.30, "put")
    assert put_itm == 20.0


def test_black_scholes_theta_decay():
    """测试时间价值衰减 (Theta Decay): DTE 越短，期权时间价值越低"""
    s = 100.0
    k = 105.0 # OTM Call
    r = 0.045
    sigma = 0.30

    price_30d = black_scholes_price(s, k, 30, r, sigma, "call")
    price_15d = black_scholes_price(s, k, 15, r, sigma, "call")
    price_2d = black_scholes_price(s, k, 2, r, sigma, "call")

    assert price_30d > price_15d > price_2d


def test_calculate_greeks_properties():
    """测试希腊字母基本数学特性"""
    s = 100.0
    k = 100.0
    t_days = 30
    r = 0.045
    sigma = 0.30

    # Call Greeks
    call_greeks = calculate_greeks(s, k, t_days, r, sigma, "call")
    assert 0.45 <= call_greeks["delta"] <= 0.65  # ATM Call Delta 约在 0.5 左右
    assert call_greeks["gamma"] > 0.0           # Long option Gamma > 0
    assert call_greeks["vega"] > 0.0            # Long option Vega > 0
    assert call_greeks["theta"] < 0.0           # Long option Theta < 0 (时间价值流逝)

    # Put Greeks
    put_greeks = calculate_greeks(s, k, t_days, r, sigma, "put")
    assert -0.65 <= put_greeks["delta"] <= -0.35 # ATM Put Delta 约在 -0.5 左右
    assert pytest.approx(put_greeks["gamma"], rel=1e-3) == call_greeks["gamma"]
    assert pytest.approx(put_greeks["vega"], rel=1e-3) == call_greeks["vega"]


def test_options_engine_class():
    """测试 OptionsEngine 封装类"""
    engine = OptionsEngine(risk_free_rate=0.045)
    p = engine.price(underlying_price=200.0, strike=204.0, dte=28, iv=0.40, option_type="call")
    assert p > 0.0

    g = engine.greeks(underlying_price=200.0, strike=204.0, dte=28, iv=0.40, option_type="call")
    assert "delta" in g and "gamma" in g and "theta" in g and "vega" in g
