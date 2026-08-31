import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskGuard:
    """
    确定性硬风控网关：
    - 正股单仓上限 <= 10%
    - 期权单笔权利金 <= 2.0%，活跃期权总占用 <= 10.0%
    - 单一板块敞口 <= 30.0%
    - 日内累计浮亏熔断 <= 5.0%
    """

    def __init__(
        self,
        max_stock_pos_pct: float = 0.1,  # max_position_pct 变更为正股专用
        max_option_cost_pct: float = 0.020,  # 期权单笔权利金
        max_total_options_pct: float = 0.100,  # 期权总持仓敞口
        max_sector_pct: float = 0.30,  # 板块总敞口
        max_daily_drawdown_pct: float = 0.05,  # 日内累计浮亏熔断
        max_position_pct: Optional[float] = None,  # 向后兼容属性，如果传入则覆盖 max_stock_pos_pct
    ):
        self.max_stock_pos_pct = max_position_pct if max_position_pct is not None else max_stock_pos_pct
        self.max_option_cost_pct = max_option_cost_pct
        self.max_total_options_pct = max_total_options_pct
        self.max_sector_pct = max_sector_pct
        self.max_daily_drawdown_pct = max_daily_drawdown_pct

    @property
    def max_position_pct(self) -> float:
        """向后兼容属性"""
        return self.max_stock_pos_pct

    @max_position_pct.setter
    def max_position_pct(self, value: float) -> None:
        self.max_stock_pos_pct = value

    def validate(
        self,
        asset_type: str = "EQUITY",  # 资产类别 'EQUITY' 或 'OPTION'
        order_amount: float = 0.0,  # 下单金额/权利金
        sector: str = "Technology",  # 标的所属板块
        total_equity: float = 1.0,  # 账户总净资产
        daily_loss_pct: float = 0.0,  # 当前累计日内浮亏百分比
        current_options_total_val: float = 0.0,  # 当前已持仓期权总市值
        sector_holdings: Optional[Dict[str, float]] = None,  # 当前各板块持仓市值字典
        **kwargs,
    ) -> Tuple[bool, List[str]]:
        """进行多维度的确定性硬风控校验并输出审计日志。

        参数:
            asset_type: 资产类别 'EQUITY' 或 'OPTION'
            order_amount: 本次下单金额 / 权利金
            sector: 标的所属板块
            total_equity: 账户总净资产
            daily_loss_pct: 当前累计日内浮亏百分比
            current_options_total_val: 当前已持仓期权总市值 (期权风控用)
            sector_holdings: 当前各板块持仓市值字典

        返回:
            (是否通过校验, 拒绝理由列表)
        """
        # 处理位置参数向后兼容调用：validate(order_amount, sector, total_equity, daily_loss_pct, sector_holdings)
        if isinstance(asset_type, (int, float)):
            # 将位置参数依次转换为正确类型的变量
            _order_amount = float(asset_type)
            _sector = str(order_amount) if isinstance(order_amount, str) else sector
            _total_equity = float(sector) if isinstance(sector, (int, float)) else total_equity
            _daily_loss_pct = float(total_equity) if isinstance(total_equity, (int, float)) else daily_loss_pct
            _sector_holdings = daily_loss_pct if isinstance(daily_loss_pct, dict) else (sector_holdings or {})
            _asset_type = kwargs.get("asset_type", "EQUITY")
            _current_options_total_val = kwargs.get("current_options_total_val", 0.0)
        else:  # 使用命名参数传递所有参数
            _asset_type = asset_type
            _order_amount = order_amount
            _sector = sector
            _total_equity = total_equity
            _daily_loss_pct = daily_loss_pct
            _current_options_total_val = current_options_total_val
            _sector_holdings = sector_holdings if sector_holdings is not None else {}

        if _total_equity <= 0:
            _total_equity = 1.0

        logger.info(
            f"[RiskGuard] 开始风控校验 -> 资产类别: {_asset_type}, 下单金额: {_order_amount:.2f}, 板块: {_sector}, "
            f"账户净资产: {_total_equity:.2f}, 当前日内浮亏: {_daily_loss_pct:.2%}"
        )

        rejections = []

        # 1. 单日累计浮亏熔断 (最高优先级)
        if _daily_loss_pct >= self.max_daily_drawdown_pct:
            reason = f"触发日内回撤熔断: 浮亏 {_daily_loss_pct:.2%} >= {self.max_daily_drawdown_pct:.2%}"
            logger.warning(f"[RiskGuard] 拒绝规则 [1/3 日内熔断] -> {reason}")
            rejections.append(reason)
        else:
            logger.debug(
                f"[RiskGuard] 通过规则 [1/3 日内熔断] -> 浮亏 {_daily_loss_pct:.2%} < 阈值 {self.max_daily_drawdown_pct:.2%}"
            )

        # 2. 资产类型仓位限额
        if _asset_type == "EQUITY":
            stock_pct = _order_amount / _total_equity
            if stock_pct > self.max_stock_pos_pct:
                reason = f"正股单仓比例 {stock_pct:.2%} > 阈值 {self.max_stock_pos_pct:.2%}"
                logger.warning(f"[RiskGuard] 拒绝规则 [2/3 正股单仓上限] -> {reason}")
                rejections.append(reason)
            else:
                logger.debug(
                    f"[RiskGuard] 通过规则 [2/3 正股单仓上限] -> 正股单仓比例 {stock_pct:.2%} <= 阈值 {self.max_stock_pos_pct:.2%}"
                )
        elif _asset_type == "OPTION":
            opt_cost_pct = _order_amount / _total_equity
            if opt_cost_pct > self.max_option_cost_pct:
                reason = f"期权单笔权利金 {opt_cost_pct:.2%} > 阈值 {self.max_option_cost_pct:.2%}"
                logger.warning(f"[RiskGuard] 拒绝规则 [2/3 期权单笔权利金] -> {reason}")
                rejections.append(reason)

            projected_total_opt_pct = (_current_options_total_val + _order_amount) / _total_equity
            if projected_total_opt_pct > self.max_total_options_pct:
                reason = f"期权总持仓敞口将达 {projected_total_opt_pct:.2%} > 阈值 {self.max_total_options_pct:.2%}"
                logger.warning(f"[RiskGuard] 拒绝规则 [2/3 期权总敞口] -> {reason}")
                rejections.append(reason)

        # 3. 单一板块敞口
        current_sector_amount = _sector_holdings.get(_sector, 0.0)
        projected_sector_pct = (current_sector_amount + _order_amount) / _total_equity
        if projected_sector_pct > self.max_sector_pct:
            reason = f"板块 [{_sector}] 总敞口 {projected_sector_pct:.2%} > 阈值 {self.max_sector_pct:.2%}"
            logger.warning(f"[RiskGuard] 拒绝规则 [3/3 板块敞口] -> {reason}")
            rejections.append(reason)
        else:
            logger.debug(
                f"[RiskGuard] 通过规则 [3/3 板块敞口] -> 预计板块 [{_sector}] 敞口 {projected_sector_pct:.2%} <= 阈值 {self.max_sector_pct:.2%}"
            )
        # 4. 总结校验结果
        passed = len(rejections) == 0
        if passed:
            logger.info(
                f"[RiskGuard] 校验通过 -> 板块 [{_sector}] 下单 {_order_amount:.2f}，预计板块敞口: {projected_sector_pct:.2%}"
            )
        else:
            logger.warning(
                f"[RiskGuard] 校验未通过 (共 {len(rejections)} 项违规) -> {'; '.join(rejections)}"
            )

        return (passed, rejections)
