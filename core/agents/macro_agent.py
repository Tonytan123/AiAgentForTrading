from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation

class MacroAgent(BaseFeatherlessAgent):
    """宏观分析智能体，专注于宏观环境与行业契合度分析。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是宏观分析智能体（Macro Agent）。

        核心任务：评估当前宏观经济环境，判断哪些行业板块与宏观经济周期高度契合，适合配置资产。

        分析框架：
        1. 宏观周期定位：
           - 扩张期：关注科技、非必需消费品等成长型板块。
           - 滞胀期：关注能源、必需消费品及公用事业等防御型板块。
           - 衰退期：关注医疗保健、必需消费品等防御型板块，规避高杠杆周期性行业。
           - 复苏期：关注金融、工业等顺周期板块。
        2. 利率与信贷：
           - 分析美联储数据、主要金融机构的贷款意愿及信用利差（HY Spread），判断资金成本与流动性松紧。
        3. 风险信号：
           - 关注 VIX 恐慌指数及 VIX 期限结构，识别市场避险情绪。
           - 监控通胀数据（CPI/PPI）及其对不同行业的影响。

        决策逻辑：
        - 基于当前宏观环境，推荐整体偏好的资产配置方向（例如：偏向防御型、偏向成长型）。
        - 识别与当前宏观环境最契合的行业板块。
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