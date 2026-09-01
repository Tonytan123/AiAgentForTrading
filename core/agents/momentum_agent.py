from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation


class MomentumAgent(BaseFeatherlessAgent):
    """动量交易智能体，专注于捕捉趋势和动量。"""

    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是动量交易研究智能体（Momentum Agent），负责评估标的资产的短线与中线做多趋势强度。

        【核心任务】
        评估标的资产是否具备强劲且健康的“做多动量（Long Momentum）与顺势买入价值”。

        【分析依据与特征】
        1. 均线趋势：价格站上 SMA20（price > sma_20）为短线多头确立。
        2. 动量健康度 (RSI)：
           - 45 <= RSI <= 65: 健康多头动量区间（最佳做多形态）；
           - RSI > 75: 严重超买，需扣分防范短线见顶回调风险；
           - RSI < 40: 弱势空头区间，不予推荐。
        3. 放量确认：成交量放大倍数 volume_surge >= 1.3x 视为有效突破信号。
        4. 日内动能：日内涨幅 (change_pct > 0) 提供动量加速度。

        【打分基准与置信度语义 (Score 0.0 ~ 1.0)】
        - 0.85 ~ 1.00: 强烈建议做多 (站上 SMA20 + 明显放量 + RSI 处于健康多头区 + 日内上涨)
        - 0.70 ~ 0.84: 动量偏多 (顺势向上，符合基本入场条件，但放量或弹性稍弱)
        - 0.50 ~ 0.69: 中性震荡 / 动量平稳 (无明显突破信号)
        - 0.00 ~ 0.49: 弱势下行或超买风险严重，禁止做多

        【输出格式】
        严格仅以 JSON 格式输出: {"score": <0.0~1.0浮点数>, "rationale": "<50字以内精炼理由>"}
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
