"""Market regime detection engine using VIX and FRED credit spreads."""

from dataclasses import dataclass
import io
import urllib.request
import pandas as pd
import yfinance as yf


@dataclass
class RegimeState:
    """Dataclass representing the current market regime and strategy weight distribution."""

    vix: float
    hy_spread: float
    is_risk_off: bool
    momentum_weight: float  # 动量/趋势策略的配置权重系数
    macro_weight: float  # 宏观/基本面策略的配置权重系数
    contrarian_weight: float  # 逆向/反转策略的配置权重系数


class RegimeEngine:
    """Evaluates real-time macro indicators to determine risk regime and strategy allocation."""

    def __init__(self, vix_threshold: float = 20.0, hy_spread_threshold: float = 10.0):
        self.vix_threshold = vix_threshold
        self.hy_spread_threshold = hy_spread_threshold

    def _fetch_hy_spread(self, default_val: float = 3.8) -> float:
        """拉取美联储 FRED 高收益信用利差 (BAMLH0A0HYM2).

        使用 FRED 官方公开数据接口，若网络异常或休市无数据则降级使用 default_val 兜底。
        """
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                content = resp.read().decode("utf-8")
            df = pd.read_csv(io.StringIO(content))
            # 清洗 FRED 在假日等缺失值时填充的 '.' 字符
            df = df[df["BAMLH0A0HYM2"] != "."]
            if not df.empty:
                return float(df["BAMLH0A0HYM2"].iloc[-1])
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
            pass
        return default_val

    def determine_regime(self, vix: float, hy_spread: float) -> str:
        """根据 VIX 与信用利差裁定宏观体制 (Regime)"""
        if vix > self.vix_threshold or hy_spread > self.hy_spread_threshold:
            if vix > 30.0:
                return "Panic_Crisis"
            return "High_Vol_Bear"
        if vix < 18.0 and hy_spread < 4.0:
            return "Bull_Trend"
        return "Neutral_Range"

    def get_strategy_weights(self, regime: str) -> dict:
        """根据当前宏观体制分配 5 大策略的权重系数"""
        if regime in ["Panic_Crisis", "High_Vol_Bear"]:
            return {
                "Momentum Agent": 0.10,
                "Macro Agent": 0.40,
                "StatArb Agent": 0.20,
                "Contrarian Agent": 0.25,
                "Exotic Agent": 0.05,
                "momentum": 0.10,
                "macro": 0.40,
                "statarb": 0.20,
                "contrarian": 0.25,
                "exotic": 0.05,
            }
        if regime == "Bull_Trend":
            return {
                "Momentum Agent": 0.45,
                "Macro Agent": 0.20,
                "StatArb Agent": 0.15,
                "Contrarian Agent": 0.10,
                "Exotic Agent": 0.10,
                "momentum": 0.45,
                "macro": 0.20,
                "statarb": 0.15,
                "contrarian": 0.10,
                "exotic": 0.10,
            }
        return {
            "Momentum Agent": 0.25,
            "Macro Agent": 0.25,
            "StatArb Agent": 0.20,
            "Contrarian Agent": 0.20,
            "Exotic Agent": 0.10,
            "momentum": 0.25,
            "macro": 0.25,
            "statarb": 0.20,
            "contrarian": 0.20,
            "exotic": 0.10,
        }

    def fetch_regime(self) -> RegimeState:
        """Fetch real-time indicators and calculate market regime state."""
        # 1. 获取 VIX 数据
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="5d")
        vix_val = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 16.5

        # 2. 拉取 FRED 信用利差 (BAMLH0A0HYM2，包含安全兜底)
        hy_spread_val = self._fetch_hy_spread(default_val=3.8)

        is_risk_off = (vix_val > self.vix_threshold) or (
            hy_spread_val > self.hy_spread_threshold
        )

        if is_risk_off:
            return RegimeState(
                vix=vix_val,
                hy_spread=hy_spread_val,
                is_risk_off=True,
                momentum_weight=0.20,
                macro_weight=0.50,
                contrarian_weight=0.30,
            )

        return RegimeState(
            vix=vix_val,
            hy_spread=hy_spread_val,
            is_risk_off=False,
            momentum_weight=0.50,
            macro_weight=0.30,
            contrarian_weight=0.20,
        )

