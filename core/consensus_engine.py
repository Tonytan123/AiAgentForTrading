import operator
import time
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel
from langgraph.graph import END, START, StateGraph

from core.agents.base_agent import AgentEvaluation
from core.agents.contrarian_agent import ContrarianAgent
from core.agents.exotic_agent import ExoticAgent
from core.agents.macro_agent import MacroAgent
from core.agents.momentum_agent import MomentumAgent
from core.agents.statarb_agent import StatArbAgent


class InvestmentMemo(BaseModel):
    proposal_id: str  # 交易建议id
    ticker: str  # 股票代码
    action: str  # 交易方向 BUY/SELL
    current_price: float  # 当前价格
    suggested_shares: int  # 建议买入股数
    total_amount: float  # 建议买入金额
    position_pct: float  # 持仓比例
    leverage: float  # 杠杆率
    take_profit_price: float  # 止盈价
    stop_loss_price: float  # 止损价
    consensus_score: float  # 加权共识评分
    agent_evaluations: List[AgentEvaluation]


class ConsensusState(TypedDict):
    ticker: str
    current_price: float
    total_equity: float
    strategy_weights: Dict[str, float]
    market_data: Dict[str, Any]
    evaluations: Annotated[List[AgentEvaluation], operator.add]
    consensus_score: float
    investment_memo: Optional[InvestmentMemo]


class ConsensusEngine:
    """基于 LangGraph 状态图的多智能体共识决策引擎"""

    def __init__(self, **agent_kwargs):
        self.agents = {
            "Momentum Agent": MomentumAgent(**agent_kwargs),
            "Macro Agent": MacroAgent(**agent_kwargs),
            "StatArb Agent": StatArbAgent(**agent_kwargs),
            "Contrarian Agent": ContrarianAgent(**agent_kwargs),
            "Exotic Agent": ExoticAgent(**agent_kwargs),
        }
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建 LangGraph 状态图：5个 Agent 并行评估 -> 汇总加权评分生成备忘录"""
        builder = StateGraph(ConsensusState)

        # 注册 5 个 Agent 节点
        builder.add_node("momentum_agent", self._momentum_node)
        builder.add_node("macro_agent", self._macro_node)
        builder.add_node("statarb_agent", self._statarb_node)
        builder.add_node("contrarian_agent", self._contrarian_node)
        builder.add_node("exotic_agent", self._exotic_node)

        # 注册汇总决策节点
        builder.add_node("aggregate_consensus", self._aggregate_node)

        # START 并行分发到 5 个 Agent 节点 (Fan-out)
        builder.add_edge(START, "momentum_agent")
        builder.add_edge(START, "macro_agent")
        builder.add_edge(START, "statarb_agent")
        builder.add_edge(START, "contrarian_agent")
        builder.add_edge(START, "exotic_agent")

        # 5 个 Agent 执行完毕后汇聚到 aggregate_consensus 节点 (Fan-in)
        builder.add_edge("momentum_agent", "aggregate_consensus")
        builder.add_edge("macro_agent", "aggregate_consensus")
        builder.add_edge("statarb_agent", "aggregate_consensus")
        builder.add_edge("contrarian_agent", "aggregate_consensus")
        builder.add_edge("exotic_agent", "aggregate_consensus")

        # 汇总决策完成后到达 END
        builder.add_edge("aggregate_consensus", END)

        return builder.compile()

    async def _momentum_node(self, state: ConsensusState) -> Dict[str, Any]:
        data = state.get("market_data", {}).get("momentum", {})
        evaluation = await self.agents["Momentum Agent"].evaluate(state["ticker"], data)
        return {"evaluations": [evaluation]}

    async def _macro_node(self, state: ConsensusState) -> Dict[str, Any]:
        data = state.get("market_data", {}).get("macro", {})
        evaluation = await self.agents["Macro Agent"].evaluate(state["ticker"], data)
        return {"evaluations": [evaluation]}

    async def _statarb_node(self, state: ConsensusState) -> Dict[str, Any]:
        data = state.get("market_data", {}).get("statarb", {})
        evaluation = await self.agents["StatArb Agent"].evaluate(state["ticker"], data)
        return {"evaluations": [evaluation]}

    async def _contrarian_node(self, state: ConsensusState) -> Dict[str, Any]:
        data = state.get("market_data", {}).get("contrarian", {})
        evaluation = await self.agents["Contrarian Agent"].evaluate(state["ticker"], data)
        return {"evaluations": [evaluation]}

    async def _exotic_node(self, state: ConsensusState) -> Dict[str, Any]:
        data = state.get("market_data", {}).get("exotic", {})
        evaluation = await self.agents["Exotic Agent"].evaluate(state["ticker"], data)
        return {"evaluations": [evaluation]}

    async def _aggregate_node(self, state: ConsensusState) -> Dict[str, Any]:
        evaluations = state.get("evaluations", [])
        strategy_weights = state.get("strategy_weights", {})
        ticker = state["ticker"]
        current_price = state["current_price"]
        total_equity = state["total_equity"]

        # 加权共识评分计算
        weighted_score = sum(e.score * strategy_weights.get(e.agent_name, 0.6) for e in evaluations)
        total_weight = sum(strategy_weights.get(e.agent_name, 0.6) for e in evaluations)
        consensus_score = round(weighted_score / total_weight, 4) if total_weight > 0 else 0.0

        memo: Optional[InvestmentMemo] = None
        # 加权总分 >= 0.70 输出交易备忘录提案
        if consensus_score >= 0.70:
            target_amount = total_equity * 0.048  # 4.8% 建议持仓
            suggested_shares = int(target_amount // current_price)
            actual_amount = suggested_shares * current_price

            memo = InvestmentMemo(
                proposal_id=f"PROP-{time.strftime('%Y%m%d')}-{ticker}-01",
                ticker=ticker,
                action="BUY",
                current_price=current_price,
                suggested_shares=suggested_shares,
                total_amount=round(actual_amount, 2),
                position_pct=round(actual_amount / total_equity, 4),
                leverage=1.0,
                take_profit_price=round(current_price * 1.080, 2),  # TP: +8.0%
                stop_loss_price=round(current_price * 0.960, 2),  # SL: -4.0%
                consensus_score=consensus_score,
                agent_evaluations=evaluations,
            )

        return {
            "consensus_score": consensus_score,
            "investment_memo": memo,
        }

    async def debate_and_aggregate(
        self,
        ticker: str,
        current_price: float,
        total_equity: float,
        strategy_weights: Dict[str, float],
        market_data: Dict[str, Any],
    ) -> Optional[InvestmentMemo]:
        """通过 LangGraph 状态图调度智能体评估与共识汇总"""
        initial_state: ConsensusState = {
            "ticker": ticker,
            "current_price": current_price,
            "total_equity": total_equity,
            "strategy_weights": strategy_weights,
            "market_data": market_data,
            "evaluations": [],
            "consensus_score": 0.0,
            "investment_memo": None,
        }

        result = await self.graph.ainvoke(initial_state)
        return result.get("investment_memo")
