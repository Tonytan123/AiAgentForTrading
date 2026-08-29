# core/regime_engine.py
from dataclasses import dataclass
import pandas as pd
import yfinance as yf


@dataclass
class RegimeState:
    vix: float
    hy_spread: float
    is_risk_off: bool
    momentum_weight: float #动量/趋势策略的配置权重系数
    macro_weight: float #宏观/基本面策略的配置权重系数
    contrarian_weight: float #逆向/反转策略的配置权重系数

class RegimeEngine:
    def __init__(self, vix_threshold: float = 20.0, hy_spread_threshold: float = 10.0):
        self.vix_threshold = vix_threshold
        self.hy_spread_threshold = hy_spread_threshold

    def _fetch_hy_spread(self, default_val: float = 3.8) -> float:
        """拉取美联储 FRED 高收益信用利差 (BAMLH0A0HYM2)
        使用 FRED 官方公开数据接口，若网络异常或休市无数据则降级使用 default_val 兜底。
        """
        try:
            import io
            import urllib.request
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                content = resp.read().decode("utf-8")
            df = pd.read_csv(io.StringIO(content))
            # 清洗 FRED 在假日等缺失值时填充的 '.' 字符
            df = df[df["BAMLH0A0HYM2"] != "."]
            if not df.empty:
                return float(df["BAMLH0A0HYM2"].iloc[-1])
        except Exception:
            pass
        return default_val


    def fetch_regime(self) -> RegimeState:
        # 1. 获取 VIX 数据
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="5d")
        # todo：此处需要改进，如果为空，直接用一个历史值16.5 mock了，后续需要优化
        vix_val = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 16.5

        # 2. 拉取 FRED 信用利差 (BAMLH0A0HYM2，包含安全兜底)
        hy_spread_val = self._fetch_hy_spread(default_val=3.8)


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
