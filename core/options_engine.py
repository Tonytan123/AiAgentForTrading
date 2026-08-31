"""
core/options_engine.py
期权定价与希腊字母计算引擎 (Black-Scholes 模型)
"""

import math
from typing import Dict, Any, Optional
from scipy.stats import norm


def black_scholes_price(
    s: float,           # 正股价格 (Underlying Price)
    k: float,           # 行权价 (Strike Price)
    t_days: int,        # 剩余到期天数 (DTE)
    r: float,           # 无风险年化利率 (Risk-free Rate, e.g. 0.045)
    sigma: float,       # 隐含波动率 (Implied Volatility, e.g. 0.35)
    option_type: str = "call"
) -> float:
    """
    计算欧式期权的 Black-Scholes 理论价格
    """
    if t_days <= 0 or s <= 0 or k <= 0 or sigma <= 0:
        intrinsic = (s - k) if option_type.lower() == "call" else (k - s)
        return max(0.0, float(intrinsic))

    t = t_days / 365.0
    d1 = (math.log(s / k) + (r + 0.5 * (sigma ** 2)) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)

    if option_type.lower() == "call":
        price = s * norm.cdf(d1) - k * math.exp(-r * t) * norm.cdf(d2)
    else:
        price = k * math.exp(-r * t) * norm.cdf(-d2) - s * norm.cdf(-d1)

    return max(0.01, float(price))


def calculate_greeks(
    s: float,
    k: float,
    t_days: int,
    r: float,
    sigma: float,
    option_type: str = "call"
) -> Dict[str, float]:
    """
    计算期权的核心希腊字母 (Delta, Gamma, Theta, Vega, Rho)
    """
    if t_days <= 0 or s <= 0 or k <= 0 or sigma <= 0:
        is_call = option_type.lower() == "call"
        delta = 1.0 if (is_call and s > k) else (-1.0 if (not is_call and s < k) else 0.0)
        return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

    t = t_days / 365.0
    sqrt_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r + 0.5 * (sigma ** 2)) * t) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    pdf_d1 = norm.pdf(d1)
    is_call = option_type.lower() == "call"

    # Delta
    delta = norm.cdf(d1) if is_call else (norm.cdf(d1) - 1.0)

    # Gamma (同一份资产 Call 和 Put 的 Gamma 相同)
    gamma = pdf_d1 / (s * sigma * sqrt_t)

    # Vega (每 1% 波动率变动对应的价格变动)
    vega = s * pdf_d1 * sqrt_t * 0.01

    # Theta (日 Theta)
    if is_call:
        theta_annual = -(s * pdf_d1 * sigma) / (2 * sqrt_t) - r * k * math.exp(-r * t) * norm.cdf(d2)
    else:
        theta_annual = -(s * pdf_d1 * sigma) / (2 * sqrt_t) + r * k * math.exp(-r * t) * norm.cdf(-d2)
    theta_daily = theta_annual / 365.0

    # Rho
    if is_call:
        rho = k * t * math.exp(-r * t) * norm.cdf(d2) * 0.01
    else:
        rho = -k * t * math.exp(-r * t) * norm.cdf(-d2) * 0.01

    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta_daily),
        "vega": float(vega),
        "rho": float(rho)
    }


class OptionsEngine:
    """
    期权引擎：统一管理期权估值、敏感度计算及合约参数推导
    """

    def __init__(self, risk_free_rate: float = 0.045):
        self.risk_free_rate = risk_free_rate

    def price(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str = "call"
    ) -> float:
        return black_scholes_price(
            s=underlying_price,
            k=strike,
            t_days=dte,
            r=self.risk_free_rate,
            sigma=iv,
            option_type=option_type
        )

    def greeks(
        self,
        underlying_price: float,
        strike: float,
        dte: int,
        iv: float,
        option_type: str = "call"
    ) -> Dict[str, float]:
        return calculate_greeks(
            s=underlying_price,
            k=strike,
            t_days=dte,
            r=self.risk_free_rate,
            sigma=iv,
            option_type=option_type
        )
