from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation

class ExoticAgent(BaseFeatherlessAgent):
    """事件驱动型智能体，专注于利用特定事件窗口獲取收益。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是事件驱动型智能体（Exotic Agent）。

        核心任务：捕捉市场中的特定事件（如财报、分红、解禁、重要经济数据发布等），并利用这些事件带来的价格异动进行交易。

        分析框架：
        1. 二元财报窗口交易（Binary Event Trading）：
           - 识别“卖空型财报”：关注 QCOM 等公司，其财报发布后通常股价下跌，形成賣空机会。
           - 识别“利好型财报”：寻找在财报前股价已被充分压制，财报发布后股价超预期反弹的機會。
           - 关注財报窗口对冲：利用不同行业财报発表时间的错位，通过对冲策略减少市场风险。
        2. 日历效应（Calendar Effects）：
           - 分析 January Effect（一月效应）：关注小型股在年初的表现。
           - 关注月末/季末效应：识别月末资金流向对股价的影响。
        3. 异常期权成交（Abnormal Options Activity）：
           - 监控异常期权成交突增形态，特别是涉及看涨期权（Call Options）的异常活动，这可能预示着大额资金的流入或对沖行为。

        决策逻辑：
        - 严格设定事件发生前后的持仓周期，避免事件后的不确定性。
        - 仓位控制：基于事件影响程度和价格波动风险设定仓位。
        - 盈利目标：在事件驱动的快速价格变动中迅速获利，或利用期权 vega 变化进行套利。
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