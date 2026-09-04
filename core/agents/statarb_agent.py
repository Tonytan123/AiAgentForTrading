from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation
from cli.i18n import get_current_lang

class StatArbAgent(BaseFeatherlessAgent):
    """统计套利智能体，专注于均值回归策略。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是统计套利与均值回归智能体（StatArb Agent），专注于度量价格相对于均值通道的偏离程度与均值回归机会。

        【核心任务】
        评估标的资产是否处于合理的均值通道内，或是否具备向上的均值回归（Mean Reversion）修复动能。

        【分析依据与特征】
        1. 价差标准化偏离度 (spread_zscore):
           - -1.5 <= spread_zscore <= 1.0: 处于健康的均线通道内，趋势运行平稳；
           - spread_zscore < -1.5: 处于过度负向偏离状态，具备强烈的均值向上回归反弹动能；
           - spread_zscore > 1.5: 处于过度正向偏离（乖离率过大），存在向下跌落均值的回踩风险。
        2. 基准联动性 (benchmark, rolling_corr):
           - rolling_corr >= 0.75: 与标杆指数（SPY）联动稳定，统计偏离具有高度回归可信度；
           - rolling_corr < 0.60: 相关性偏低或脱钩，套利有效性降低。

        【打分基准与置信度语义 (Score 0.0 ~ 1.0)】
        - 0.80 ~ 1.00: 均值回归做多良机 (健康均线通道内，或深跌负偏离且相关性强)
        - 0.70 ~ 0.79: 通道平稳 (偏离度可控，符合正常波动规律)
        - 0.50 ~ 0.69: 偏离度较高或相关性偏弱 (需防范震荡)
        - 0.00 ~ 0.49: 严重正向过度透支或协整破位，不宜追高买入

        【输出格式】
        严格仅以 JSON 格式输出: {"score": <0.0~1.0浮点数>, "rationale": "<50字以内精炼理由>"}
        """
        super().__init__(name="StatArb Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """统计套利智能体量化启发式评估模型"""
        spread_zscore = float(context_data.get("spread_zscore", 0.0))
        rolling_corr = float(context_data.get("rolling_corr", 0.80))
        is_en = get_current_lang() == "en"

        if -1.5 <= spread_zscore <= 1.0:
            score = 0.80
            rat = (
                f"Spread Z-Score={spread_zscore:.2f} in healthy channel (Corr={rolling_corr:.2f})"
                if is_en
                else f"价差Z-Score={spread_zscore:.2f}处于健康均值通道 (相关性={rolling_corr:.2f})"
            )
        elif spread_zscore < -1.5:
            score = 0.72
            rat = (
                f"Spread Z-Score={spread_zscore:.2f} negative deviation, upward mean reversion dynamic"
                if is_en
                else f"价差Z-Score={spread_zscore:.2f}处于负向偏离，具备均值回归向上动能"
            )
        else:
            score = 0.50
            rat = (
                f"Spread Z-Score={spread_zscore:.2f} elevated, wide mean divergence"
                if is_en
                else f"价差Z-Score={spread_zscore:.2f}偏高，均线偏离度过大"
            )

        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)