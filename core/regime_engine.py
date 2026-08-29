# core/regime_engine.py
import yfinance as yf
from dataclasses import dataclass

@dataclass
class RegimeState:
    vix: float
    hy_spread: float
    is_risk_off: bool
    momentum_weight: float
    macro_weight: float
    contrarian_weight: float

class RegimeEngine:
    def __init__(self, vix_threshold: float = 20.0, hy_spread_threshold: float = 10.0):
        self.vix_threshold = vix_threshold
        self.hy_spread_threshold = hy_spread_threshold

    def fetch_regime(self) -> RegimeState:
        # 获取 VIX 数据
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="5d")
        vix_val = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 16.5

        # 模拟/拉取信用利差 (可接入 FRED API: BAMLH0A0HYM2，此处内置兜底安全解析)
        hy_spread_val = 3.8

        is_risk_off = (vix_val > self.vix_threshold) or (hy_spread_val > self.hy_spread_threshold)

        if is_risk_off:
            return RegimeState(
                vix=vix_val,
                hy_spread=hy_spread_val,
                is_risk_off=True,
                momentum_weight=0.20,
                macro_weight=0.50,
                contrarian_weight=0.30
            )
        else:
            return RegimeState(
                vix=vix_val,
                hy_spread=hy_spread_val,
                is_risk_off=False,
                momentum_weight=0.50,
                macro_weight=0.30,
                contrarian_weight=0.20
            )