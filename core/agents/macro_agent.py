from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation

class MacroAgent(BaseFeatherlessAgent):
    """宏观分析智能体，专注于宏观环境与行业契合度分析。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是宏观基本面研究智能体（Macro Agent），负责评估当前宏观经济环境、波动率及信用流动性是否支持开仓做多。

        【核心任务】
        从宏观顶层自上而下评估市场风险偏好，判断大环境是否适合配置多头资产。

        【分析依据与特征】
        1. 宏观体制 (regime)：
           - Bull_Trend (低波多头牛市): 市场风险偏好极佳，全面顺势做多；
           - Neutral_Range (中性震荡): 精选低波与稳健行业，控制仓位；
           - High_Vol_Bear (高波熊市): 宏观环境承压，需严格防守，减少做多；
           - Panic_Crisis (恐慌危机): 流动性紧缩与系统性风险，严禁盲目做多。
        2. 波动率指数 (VIX):
           - VIX < 18.0: 波动率平稳低迷，极利于多头趋势延续；
           - 18.0 <= VIX <= 22.0: 适度波动，风险可控；
           - VIX > 25.0: 恐慌避险情绪升温，多头资产面临剧烈震荡。
        3. 高收益债信用利差 (hy_spread):
           - hy_spread < 4.0%: 信用环境宽松，企业偿债风险低；
           - hy_spread > 5.5%: 信用利差走阔，流动性收紧。

        【打分基准与置信度语义 (Score 0.0 ~ 1.0)】
        - 0.85 ~ 1.00: 宏观极佳 (低波牛市 + VIX < 18 + 信用环境良好，全力做多)
        - 0.70 ~ 0.84: 宏观中性偏多 (震荡但整体平稳，适合精选标的开仓)
        - 0.45 ~ 0.69: 宏观偏空或波动率偏高 (VIX > 22，应谨慎防守)
        - 0.00 ~ 0.44: 宏观恐慌危机 (流动性冲击，严禁开仓)

        【输出格式】
        严格仅以 JSON 格式输出: {"score": <0.0~1.0浮点数>, "rationale": "<50字以内精炼理由>"}
        """
        super().__init__(name="Macro Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """宏观智能体量化启发式评估模型"""
        regime = context_data.get("regime", "Bull_Trend")
        vix = float(context_data.get("vix", 18.0))

        if regime == "Bull_Trend":
            score = 0.88
            rat = f"宏观处于稳定低波多头 (VIX={vix:.1f})，顺势看多"
        elif regime == "Neutral_Range":
            score = 0.75
            rat = f"宏观处于中性震荡区间 (VIX={vix:.1f})，精选优质资产"
        elif regime == "High_Vol_Bear":
            score = 0.45
            rat = f"宏观高波偏空 (VIX={vix:.1f})，需严格防守"
        else:
            score = 0.20
            rat = f"宏观恐慌危机 (VIX={vix:.1f})，严禁盲目做多"

        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)