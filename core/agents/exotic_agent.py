from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation

class ExoticAgent(BaseFeatherlessAgent):
    """事件驱动型智能体，专注于利用特定事件窗口獲取收益。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是衍生品与事件驱动研究智能体（Exotic Agent），专注于评估二元财报事件风险、期权隐波及衍生品结构优势。

        【核心任务】
        评估标的资产在未来窗口期内是否能够安全避开重大二元事件风险（如财报黑天鹅），以及是否具备衍生品/期权做多性价比。

        【分析依据与特征】
        1. 二元财报距离天数 (days_to_earnings):
           - days_to_earnings > 14 天: 财报窗口安全，彻底规避财报突发暴跌与隐波挤压（IV Crush）风险；
           - 8 ~ 14 天: 临近财报观察期，需关注波动率变化；
           - <= 7 天: 处于重大二元财报高危静默期，严禁无保护做多，必须严格扣分。
        2. 隐含波动率 (implied_vol):
           - 评估期权权利金定价贵贱，IV 适中（30%~45%）有利于构建高性价比价差组合。
        3. 看跌看涨期权比率 (pcr):
           - PCR 处于 0.6 ~ 0.9 为健康看涨筹码结构。

        【打分基准与置信度语义 (Score 0.0 ~ 1.0)】
        - 0.80 ~ 1.00: 事件风险低且衍生品结构良好 (days_to_earnings > 14 天 + IV 适中)
        - 0.65 ~ 0.79: 事件窗口相对安全 (days_to_earnings 10~14 天，基本无重大事件阻碍)
        - 0.40 ~ 0.64: 临近二元财报窗口 (days_to_earnings 8~10 天，存在一定事件波动风险)
        - 0.00 ~ 0.39: 极度临近财报 (days_to_earnings <= 7 天)，存在二元黑天鹅风险，严禁做多

        【输出格式】
        严格仅以 JSON 格式输出: {"score": <0.0~1.0浮点数>, "rationale": "<50字以内精炼理由>"}
        """
        super().__init__(name="Exotic Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """衍生品/事件驱动智能体量化启发式评估模型"""
        days_to_earnings = int(context_data.get("days_to_earnings", 30))
        implied_vol = float(context_data.get("implied_vol", 0.35))

        if days_to_earnings > 14:
            score = 0.80
            rat = f"财报窗口尚有 {days_to_earnings} 天，规避二元事件风险 (IV={implied_vol:.1%})"
        else:
            score = 0.55
            rat = f"临近二元财报窗口 ({days_to_earnings}天)，存在事件波动率风险"

        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)