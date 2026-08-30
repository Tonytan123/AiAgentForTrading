import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class RiskGuard:
    """确定性硬风控网关：单仓上限 <=10%、板块上限 <=30.0%、单日回撤 <=9.0%"""

    def __init__(
        self,
        max_position_pct: float = 0.10,
        max_sector_pct: float = 0.30,
        max_daily_drawdown_pct: float = 0.09,
    ):
        self.max_position_pct = max_position_pct
        self.max_sector_pct = max_sector_pct
        self.max_daily_drawdown_pct = max_daily_drawdown_pct

    def validate(
        self,
        order_amount: float,
        sector: str,
        total_equity: float,
        daily_loss_pct: float,
        sector_holdings: Dict[str, float],
    ) -> Tuple[bool, List[str]]:
        """进行多维度的风控校验并输出审计日志。

        参数:
            order_amount: 本次下单金额
            sector: 股票所属板块
            total_equity: 账户总净资产
            daily_loss_pct: 当前累计日内浮亏百分比
            sector_holdings: 当前各板块持仓市值字典

        返回:
            (是否通过校验, 拒绝理由列表)
        """
        logger.info(
            f"[RiskGuard] 开始风控校验 -> 下单金额: {order_amount:.2f}, 板块: {sector}, "
            f"账户净资产: {total_equity:.2f}, 当前日内浮亏: {daily_loss_pct:.2%}"
        )

        rejections = []

        # 1. 单日累计浮亏熔断校验 (最高优先级，触及则熔断所有交易)
        if daily_loss_pct >= self.max_daily_drawdown_pct:
            reason = f"触发当日回撤熔断: 累计浮亏 {daily_loss_pct:.2%} >= {self.max_daily_drawdown_pct:.2%}"
            logger.warning(f"[RiskGuard] 拒绝规则 [1/3 日内熔断] -> {reason}")
            rejections.append(reason)
        else:
            logger.debug(
                f"[RiskGuard] 通过规则 [1/3 日内熔断] -> 累计浮亏 {daily_loss_pct:.2%} < 阈值 {self.max_daily_drawdown_pct:.2%}"
            )

        # 2. 单仓上限校验 (防止单一标的风险过高)
        pos_pct = order_amount / total_equity if total_equity > 0 else 1.0
        if pos_pct > self.max_position_pct:
            reason = f"单仓比例 {pos_pct:.2%} 超过硬风控阈值 {self.max_position_pct:.2%}"
            logger.warning(f"[RiskGuard] 拒绝规则 [2/3 单仓上限] -> {reason}")
            rejections.append(reason)
        else:
            logger.debug(
                f"[RiskGuard] 通过规则 [2/3 单仓上限] -> 单仓比例 {pos_pct:.2%} <= 阈值 {self.max_position_pct:.2%}"
            )

        # 3. 单一板块敞口校验 (防止行业集中度过高)
        current_sector_amount = sector_holdings.get(sector, 0.0)
        """
        这是防止单一行业（如科技股）波动拖垮整个投资组合的关键。
        如果一个行业的持仓占比过高，即使这只股票本身风控通过，
        但一旦该行业整体下跌，风险敞口会过大。
        """
        projected_sector_pct = (current_sector_amount + order_amount) / total_equity
        if projected_sector_pct > self.max_sector_pct:
            reason = (
                f"板块 [{sector}] 敞口将达 {projected_sector_pct:.2%}，"
                f"超过上限 {self.max_sector_pct:.2%}"
            )
            logger.warning(f"[RiskGuard] 拒绝规则 [3/3 板块敞口] -> {reason}")
            rejections.append(reason)
        else:
            logger.debug(
                f"[RiskGuard] 通过规则 [3/3 板块敞口] -> 预计板块 [{sector}] 敞口 {projected_sector_pct:.2%} <= 阈值 {self.max_sector_pct:.2%}"
            )

        # 总结校验结果
        passed = len(rejections) == 0
        if passed:
            logger.info(
                f"[RiskGuard] 校验通过 -> 板块 [{sector}] 下单 {order_amount:.2f} ({pos_pct:.2%})，预计板块敞口: {projected_sector_pct:.2%}"
            )
        else:
            logger.warning(
                f"[RiskGuard] 校验未通过 (共 {len(rejections)} 项违规) -> {'; '.join(rejections)}"
            )

        return (passed, rejections)
