from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation
from cli.i18n import get_current_lang

class ContrarianAgent(BaseFeatherlessAgent):
    """逆向投资智能体，专注于在市场过度恐慌时寻找反转机会。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是逆向投资研究智能体（Contrarian Agent），专注于在市场过度恐慌与极端超卖时寻找非对称赔率的反转做多机会。

        【核心任务】
        评估标的资产是否释放了充分的看空情绪，并具备被错杀后的“左侧低吸与超跌反弹价值”。

        【分析依据与特征】
        1. 超卖反弹因子 (oversold_score, 范围 0.0 ~ 1.0):
           - oversold_score >= 0.50: 处于极端超卖区域，左侧反转胜率与赔率极高；
           - 0.20 <= oversold_score < 0.50: 回调洗盘企稳，情绪释放较为充分；
           - oversold_score < 0.20: 情绪中性或处于顺势拉升期，非逆向主要机会区。
        2. 恐慌指数 (panic_index):
           - 衡量市场情绪恐慌程度（基于 VIX 衍生），恐慌情绪见顶往往对应阶段性价格底部。
        3. 内部人与筹码 (insider_activity, pcr):
           - 内部人增持（Insider Buy）与适度看跌期权积累（PCR）提供逆向筹码支撑。

        【打分基准与置信度语义 (Score 0.0 ~ 1.0)】
        - 0.85 ~ 1.00: 绝佳逆向做多买点 (极端超卖 oversold_score >= 0.5 + 恐慌释放充分)
        - 0.70 ~ 0.84: 良好超跌企稳点 (中度超卖，具备反弹动能)
        - 0.60 ~ 0.69: 情绪平稳 / 中性态 (未出现超卖，作为中性评估)
        - 0.00 ~ 0.59: 情绪高亢极度贪婪或基本面破位（价值陷阱），禁止逆向买入

        【输出格式】
        严格仅以 JSON 格式输出: {"score": <0.0~1.0浮点数>, "rationale": "<50字以内精炼理由>"}
        """
        super().__init__(name="Contrarian Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """逆向投资智能体量化启发式评估模型"""
        oversold_score = float(context_data.get("oversold_score", 0.10))
        panic_index = float(context_data.get("panic_index", 25.0))
        is_en = get_current_lang() == "en"

        if oversold_score >= 0.50:
            score = 0.85
            rat = (
                f"Oversold rebound factor={oversold_score:.2f} (Extreme oversold), high contrarian asymmetric upside"
                if is_en
                else f"超卖反弹因子={oversold_score:.2f}处于极端超卖，逆向非对称赔率极高"
            )
        elif oversold_score >= 0.20:
            score = 0.75
            rat = "Pullback stabilized, sentiment well-flushed" if is_en else "洗盘回调企稳，情绪释放充分"
        else:
            score = 0.65
            rat = f"Neutral stable sentiment (Panic Index={panic_index:.1f})" if is_en else f"情绪中性稳定 (恐慌指数={panic_index:.1f})"

        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)