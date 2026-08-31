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

class HybridInvestmentMemo(BaseModel):
    proposal_id: str  #提案唯一业务标识符
    asset_type: str  # 'EQUITY' or 'OPTION'
    underlying_ticker: str  # 标的资产代码（如 NVDA, AAPL）
    ticker: Optional[str] = None      # 兼容字段
    action: str  # BUY / BUY_TO_OPEN
    current_underlying_price: float  #当前标的资产价格
    
    # 正股专用字段
    suggested_shares: Optional[int] = None  #建议买入股数
    stock_total_amount: Optional[float] = None  #建议买入金额

    # 期权专用字段
    contract_symbol: Optional[str] = None #期权合约代码
    option_type: Optional[str] = None # 'Call' or 'Put'
    strike_price: Optional[float] = None #行权价
    expiration_date: Optional[str] = None #到期日
    dte: Optional[int] = None #到期天数
    suggested_contracts: Optional[int] = None #建议买入期权合约数
    premium_per_share: Optional[float] = None #每股权利金
    total_premium: Optional[float] = None #总权利金
    delta: Optional[float] = None #期权希腊字母 Delta，表示标的资产价格变动1美元对期权价格的影响
    theta: Optional[float] = None #期权希腊字母 Theta，表示标的资产价格每延迟一天对期权价格的影响
    iv: Optional[float] = None #期权隐含波动率

    # 通用风控字段
    position_pct: float  #资金占比
    cost_pct: float  #权利金占比 (期权)
    take_profit_price: float  #止盈价
    stop_loss_price: float  #止损价
    consensus_score: float #共识得分
    agent_evaluations: List[AgentEvaluation] #各智能体评估详情列表

    def model_post_init(self, __context: Any) -> None:
        if self.ticker is None:
            self.ticker = self.underlying_ticker

    @property
    def current_price(self) -> float: #当前价格
        return self.current_underlying_price

    @property
    def total_amount(self) -> float: #总金额
        return self.stock_total_amount or self.total_premium or 0.0


# 别名兼容
InvestmentMemo = HybridInvestmentMemo


class ConsensusState(TypedDict):
    ticker: str #交易标的代码（如 NVDA）
    current_price: float #当前价格
    total_equity: float #总资产净值
    strategy_weights: Dict[str, float] #各智能体策略权重
    market_data: Dict[str, Any] #各智能体市场数据
    preferred_asset_type: str #首选资产类型
    evaluations: Annotated[List[AgentEvaluation], operator.add] #各智能体评估详情列表
    consensus_score: float #共识得分
    investment_memo: Optional[HybridInvestmentMemo] #投资备忘录


class ConsensusEngine:
    """基于 LangGraph 状态图的多智能体共识决策引擎 (支持正股/期权混合资产提案)"""

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
        market_data = state.get("market_data", {})
        preferred_asset_type = state.get("preferred_asset_type", "AUTO")

        # 1. 加权共识得分
        weighted_score = sum(e.score * strategy_weights.get(e.agent_name, 0.6) for e in evaluations)
        total_weight = sum(strategy_weights.get(e.agent_name, 0.6) for e in evaluations)
        consensus_score = round(weighted_score / total_weight, 4) if total_weight > 0 else 0.0

        if consensus_score < 0.70:
            return {
                "consensus_score": consensus_score,
                "investment_memo": None,
            }

        # 2. 决定资产类型 (高置信度且动量极强时优先推荐期权以小博大)
        choose_option = (preferred_asset_type == "OPTION") or (
            preferred_asset_type == "AUTO"
            and consensus_score >= 0.73
            and market_data.get("momentum", {}).get("rsi", 50) > 55
        )

        proposal_id = f"PROP-{time.strftime('%Y%m%d')}-{ticker}-{'OPT' if choose_option else 'EQ'}-01"

        if choose_option:
            # 构建期权提案 (Long Call, 限制权利金 <= 1.5% 账户总净值)
            strike = round(current_price * 1.02, 1)
            premium_est = round(current_price * 0.035, 2)
            contract_cost = premium_est * 100

            target_budget = total_equity * 0.015  # 预算 1.5% 权利金
            suggested_contracts = max(1, int(target_budget // contract_cost))
            total_premium = suggested_contracts * contract_cost

            memo = HybridInvestmentMemo(
                proposal_id=proposal_id,
                asset_type="OPTION",
                underlying_ticker=ticker,
                action="BUY_TO_OPEN",
                current_underlying_price=current_price,
                contract_symbol=f"{ticker}260918C{int(strike*1000):08d}",
                option_type="Call",
                strike_price=strike,
                expiration_date="2026-09-18",
                dte=18,
                suggested_contracts=suggested_contracts,
                premium_per_share=premium_est,
                total_premium=round(total_premium, 2),
                delta=0.58,
                theta=-0.08,
                iv=0.421,
                position_pct=round(total_premium / total_equity, 4),
                cost_pct=round(total_premium / total_equity, 4),
                take_profit_price=round(premium_est * 1.50, 2),  # 期权 TP: +50%
                stop_loss_price=round(premium_est * 0.70, 2),    # 期权 SL: -30%
                consensus_score=consensus_score,
                agent_evaluations=evaluations,
            )
        else:
            # 构建正股提案
            target_amount = total_equity * 0.048
            suggested_shares = int(target_amount // current_price)
            actual_amount = suggested_shares * current_price

            memo = HybridInvestmentMemo(
                proposal_id=proposal_id,
                asset_type="EQUITY",
                underlying_ticker=ticker,
                action="BUY",
                current_underlying_price=current_price,
                suggested_shares=suggested_shares,
                stock_total_amount=round(actual_amount, 2),
                position_pct=round(actual_amount / total_equity, 4),
                cost_pct=0.0,
                take_profit_price=round(current_price * 1.08, 2),  # 正股 TP: +8%
                stop_loss_price=round(current_price * 0.96, 2),    # 正股 SL: -4%
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
        preferred_asset_type: str = "AUTO",  # AUTO / EQUITY / OPTION
    ) -> Optional[HybridInvestmentMemo]:
        """通过 LangGraph 状态图调度智能体并行评估与混合资产共识汇总"""
        initial_state: ConsensusState = {
            "ticker": ticker,
            "current_price": current_price,
            "total_equity": total_equity,
            "strategy_weights": strategy_weights,
            "market_data": market_data,
            "preferred_asset_type": preferred_asset_type,
            "evaluations": [],
            "consensus_score": 0.0,
            "investment_memo": None,
        }

        result = await self.graph.ainvoke(initial_state)
        return result.get("investment_memo")
