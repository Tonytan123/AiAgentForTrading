from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation


class MomentumAgent(BaseFeatherlessAgent):
    """动量交易智能体，专注于捕捉趋势和动量。"""

    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是动量交易智能体（Momentum Agent）。

        核心任务：识别市场中的强势个股（Long）和弱势个股（Short），并依据动量原则给出交易建议。

        分析框架：
        1. 价格趋势：使用 20日简单移动平均线 (SMA20) 和 50日简单移动平均线 (SMA50) 判断趋势方向。
           - 上升趋势：SMA20 > SMA50 且股价 > SMA20。
           - 下降趋势：SMA20 < SMA50 且股价 < SMA20。
        2. 动量强度：使用相对强弱指数 (RSI) 评估当前动量的健康度。
           - 持续强势：RSI > 60。
           - 持续弱势：RSI < 40。
           - 价格突破：RSI 伴随价格突破关键阻力/支撑位。
        3. 波动率与风险：使用平均真实波幅 (ATR) 衡量当前波动水平，辅助止损位设定。
        4. 交易量确认：关注价格突破时的成交量是否显著放大（趋势确认信号）。

        决策逻辑：
        - 优先做多 (Long) 处于上升趋势且动量强劲的股票。
        - 优先做空 (Short) 处于下降趋势且动量疲弱的股票。
        - 避开盘整且波动率异常高的股票。
        """
        super().__init__(name="Momentum Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """动量智能体量化启发式评估模型"""
        price = float(context_data.get("price", 100.0))
        sma_20 = float(context_data.get("sma_20", price * 0.98))
        rsi = float(context_data.get("rsi", 50.0))
        vol_surge = float(context_data.get("volume_surge", 1.0))
        chg_pct = float(context_data.get("change_pct", 0.0))

        score = 0.50
        reasons = []
        if price > sma_20:
            score += 0.25
            reasons.append(f"站上SMA20 (${sma_20:.1f})")
        if chg_pct > 0:
            score += min(0.20, chg_pct * 0.05)
            reasons.append(f"日内+{chg_pct:.1f}%")
        elif chg_pct < -3.0:
            score -= 0.15
        if 40 <= rsi <= 65:
            score += 0.15
            reasons.append(f"RSI={rsi:.0f}健康多头")
        elif rsi > 75:
            score -= 0.20
        if vol_surge >= 1.3:
            score += 0.15
            reasons.append(f"放量{vol_surge:.1f}x")

        score = round(min(0.99, max(0.01, score)), 2)
        rat = " | ".join(reasons) if reasons else "动量趋势平稳"
        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)
