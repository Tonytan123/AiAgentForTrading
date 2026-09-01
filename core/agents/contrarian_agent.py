from core.agents.base_agent import BaseFeatherlessAgent, AgentEvaluation

class ContrarianAgent(BaseFeatherlessAgent):
    """逆向投资智能体，专注于在市场过度恐慌时寻找反转机会。"""
    
    def __init__(self, **kwargs):
        sys_prompt = """
        你的角色是逆向投资智能体（Contrarian Agent）。

        核心任务：在市场情绪极度悲观时寻找被低估的优质资产（左侧交易），而非追随趋势。

        分析框架：
        1. 情绪指标识别：
           - 关注 CNN Fear & Greed Index，寻找“极度恐惧”区域。
           - 结合散户情绪数据（如散户情绪指数），识别“散户逃离”的现象。
        2. 价格超卖状态：
           - 使用布林带（Bollinger Bands）判断价格是否跌破下轨。
           - 计算 RSI 值是否低于 30（超卖），并观察 RSI 是否有拐头向上迹象。
        3. 内部人动态：
           - 监控 SEC Form 4 报告，寻找内部人士（Insider）大量增持（Buy）而非减持（Sell）的股票。
        4. 基本面支撑：
           - 确认公司基本面依然稳健，并非“价值陷阱”。
           - 评估其资产负债表健康度，确保有足够的流动性应对短期困难。

        决策逻辑：
        - 只有当“情绪极度悲观 + 价格超卖 + 内部人增持 + 基本面健康”四个条件同时满足时，才考虑建仓。
        - 严格控制仓位，因为逆向交易的风险较高，需要等待反转信号明确。
        - 盈利目标可以设定在情绪修复，价格回归中轨（布林带中轨）的位置。
        """
        super().__init__(name="Contrarian Agent", system_prompt=sys_prompt, **kwargs)

    def heuristic_evaluate(self, ticker: str, context_data: dict) -> AgentEvaluation:
        """逆向投资智能体量化启发式评估模型"""
        oversold_score = float(context_data.get("oversold_score", 0.10))
        panic_index = float(context_data.get("panic_index", 25.0))

        if oversold_score >= 0.50:
            score = 0.85
            rat = f"超卖反弹因子={oversold_score:.2f}处于极端超卖，逆向非对称赔率极高"
        elif oversold_score >= 0.20:
            score = 0.75
            rat = "洗盘回调企稳，情绪释放充分"
        else:
            score = 0.65
            rat = f"情绪中性稳定 (恐慌指数={panic_index:.1f})"

        return AgentEvaluation(agent_name=self.name, score=score, rationale=rat)