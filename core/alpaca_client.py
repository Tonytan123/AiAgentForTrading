from typing import Any, Dict, List, Optional
import time
import logging
import yaml
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce, QueryOrderStatus, ContractType
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
    GetOrdersRequest,
    GetOptionContractsRequest,
    ClosePositionRequest,
)

logger = logging.getLogger(__name__)

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class AlpacaGateway:
    """Gateway interface for interacting with Alpaca Trading & Market Data APIs."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, paper: Optional[bool] = None):
        key = api_key or config.get("alpaca", {}).get("api_key")
        secret = secret_key or config.get("alpaca", {}).get("secret_key")
        is_paper = paper if paper is not None else config.get("alpaca", {}).get("paper", True)

        self.trading_client = TradingClient(
            api_key=key,
            secret_key=secret,
            paper=is_paper,
        )
        self.client = self.trading_client
        self.data_client = StockHistoricalDataClient(
            api_key=key,
            secret_key=secret,
        )

    def get_account(self):
        """Retrieve current trading account information."""
        return self.trading_client.get_account()

    def get_positions(self) -> List[Any]:
        """Retrieve all currently held open positions."""
        try:
            return self.trading_client.get_all_positions()
        except Exception as e:
            logger.warning(f"[Alpaca Error] Failed to fetch open positions: {e}")
            return []

    def get_open_orders(self, nested: bool = True) -> List[Any]:
        """Retrieve all currently active open orders."""
        try:
            req = GetOrdersRequest(status=QueryOrderStatus.OPEN, nested=nested)
            return self.trading_client.get_orders(filter=req)
        except Exception as e:
            logger.warning(f"[Alpaca Error] Failed to fetch open orders: {e}")
            return []

    def get_current_price(self, symbol: str) -> float:
        """Fetch latest market close price for the specified stock symbol."""
        req = StockLatestBarRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
        latest_bars = self.data_client.get_stock_latest_bar(req)
        if symbol in latest_bars and latest_bars[symbol] is not None:
            return float(latest_bars[symbol].close)
        raise ValueError(f"No market data found for {symbol}")

    def submit_bracket_order(
        self, symbol: str, qty: int, take_profit_price: float, stop_loss_price: float
    ):
        """Submit a bracket buy order with target take-profit and stop-loss prices."""
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2)),
        )
        return self.trading_client.submit_order(order_data=req)

    def close_position(self, symbol: str, qty: Optional[float] = None):
        """Liquidate and close an open position for a given symbol (full or partial qty)."""
        if qty is not None:
            req = ClosePositionRequest(qty=str(qty))
            return self.trading_client.close_position(symbol_or_asset_id=symbol, close_options=req)
        return self.trading_client.close_position(symbol_or_asset_id=symbol)

    def cancel_order(self, order_id: str):
        """Cancel a specific active open order by order ID."""
        return self.trading_client.cancel_order_by_id(order_id)

    def cancel_all_orders(self):
        """Cancel all active open orders."""
        return self.trading_client.cancel_orders()


    def get_account_summary(self) -> Dict[str, float]:
        """Retrieve key account metrics."""
        account = self.trading_client.get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity) if account.last_equity else equity
        return {
            "total_equity": equity,
            "buying_power": float(account.buying_power),
            "options_buying_power": float(getattr(account, "options_buying_power", account.buying_power)),
            "cash": float(account.cash),
            "day_pnl_pct": (equity - last_equity) / last_equity if last_equity > 0 else 0.0,
        }

    def place_bracket_oco_order(self, ticker: str, shares: int, take_profit_price: float, stop_loss_price: float):
        """提交 OCO (市价入场 + GTC 止盈止损)"""
        req = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_loss_price)
        )
        order = self.client.submit_order(order_data=req)
        logger.info(f"正股 Bracket OCO 订单提交成功: Symbol={ticker}, OrderID={order.id}")
        return str(order.id)

    def place_option_limit_order(
        self,
        contract_symbol: str,
        contracts: int,
        limit_price: float,
        side: OrderSide = OrderSide.BUY
    ) -> str:
        """提交期权限价单 (Limit Order @ Mid Price 防止流动性冲击)"""
        req = LimitOrderRequest(
            symbol=contract_symbol,  # 期权合约代码
            qty=contracts,  # 合约份数
            side=side,  # 买入或卖出
            time_in_force=TimeInForce.DAY,  # 设置订单的有效期限为当日有效
            limit_price=round(limit_price, 2)  # 期权订单限价
        )
        order = self.client.submit_order(order_data=req)
        logger.info(f"期权限价单提交成功: Symbol={contract_symbol}, OrderID={order.id}")
        return str(order.id)

    def get_option_contracts(
        self,
        underlying_symbol: str,
        expiration_date_gte: Optional[str] = None,
        expiration_date_lte: Optional[str] = None,
        contract_type: Optional[ContractType] = None,
        status: str = "active",
        limit: int = 100,
    ) -> List[Any]:
        """通过 Alpaca Trading API 查询指定标的真实挂牌的期权合约链"""
        try:
            req = GetOptionContractsRequest(
                underlying_symbols=[underlying_symbol],
                status=status,
                expiration_date_gte=expiration_date_gte,
                expiration_date_lte=expiration_date_lte,
                type=contract_type,
                limit=limit,
            )
            res = self.trading_client.get_option_contracts(req)
            if hasattr(res, "option_contracts") and res.option_contracts:
                return res.option_contracts
            elif isinstance(res, list):
                return res
            return []
        except Exception as e:
            logger.warning(f"[Alpaca Error] Failed to fetch {underlying_symbol} option contract chain: {e}")
            return []

    def get_best_option_contract(
        self,
        underlying_symbol: str,
        target_strike: float,
        option_type: str = "call",
        min_dte: int = 14,
        max_dte: int = 45,
    ) -> Optional[Dict[str, Any]]:
        """
        根据目标行权价与目标 DTE 窗口，从 Alpaca 真实期权链中匹配最优真实挂牌合约 (OCC 代码)
        返回符合条件的合约字典，若无匹配或网络异常则返回 None
        """
        try:
            import datetime
            today = datetime.date.today()
            date_gte = (today + datetime.timedelta(days=min_dte)).strftime("%Y-%m-%d")
            date_lte = (today + datetime.timedelta(days=max_dte)).strftime("%Y-%m-%d")
            c_type = ContractType.CALL if option_type.lower() == "call" else ContractType.PUT

            contracts = self.get_option_contracts(
                underlying_symbol=underlying_symbol,
                expiration_date_gte=date_gte,
                expiration_date_lte=date_lte,
                contract_type=c_type,
                status="active",
                limit=100,
            )
            if not contracts:
                return None

            valid_contracts = []
            for c in contracts:
                if getattr(c, "tradable", True) is False:
                    continue
                try:
                    s_price = float(c.strike_price)
                    exp_d = c.expiration_date
                    if isinstance(exp_d, str):
                        exp_date = datetime.datetime.strptime(exp_d, "%Y-%m-%d").date()
                    elif isinstance(exp_d, datetime.date):
                        exp_date = exp_d
                    else:
                        continue
                    dte = (exp_date - today).days
                    valid_contracts.append({
                        "contract": c,
                        "strike_price": s_price,
                        "expiration_date": exp_date.strftime("%Y-%m-%d"),
                        "dte": dte,
                        "strike_diff": abs(s_price - target_strike),
                    })
                except Exception:
                    continue

            if not valid_contracts:
                return None

            # 优先按行权价差距排序，次优先按 DTE 接近 30 天排序
            valid_contracts.sort(key=lambda x: (x["strike_diff"], abs(x["dte"] - 30)))
            best = valid_contracts[0]
            c_obj = best["contract"]

            return {
                "contract_symbol": str(c_obj.symbol),
                "strike_price": best["strike_price"],
                "expiration_date": best["expiration_date"],
                "dte": best["dte"],
                "option_type": "Call" if option_type.lower() == "call" else "Put",
                "close_price": float(c_obj.close_price) if getattr(c_obj, "close_price", None) else None,
            }
        except Exception as e:
            logger.warning(f"匹配 {underlying_symbol} 最优期权合约异常: {e}")
            return None

    def get_treasury_sweep_position(self, symbol: str = "SGOV") -> Optional[Dict[str, Any]]:
        """获取国债/货币基金 (如 SGOV) 的当前持仓状态 (包含总持仓与可用未锁定持仓)"""
        try:
            position = self.trading_client.get_open_position(symbol_or_asset_id=symbol)
            qty_raw = getattr(position, "qty", 0.0)
            qty_avail_raw = getattr(position, "qty_available", None)

            # 兼容 Alpaca SDK 属性及 Mock 对象
            if qty_avail_raw is not None and not hasattr(qty_avail_raw, "_mock_return_value"):
                try:
                    qty_avail = float(qty_avail_raw)
                except (ValueError, TypeError):
                    qty_avail = float(qty_raw)
            else:
                qty_avail = float(qty_raw)

            return {
                "symbol": symbol,
                "qty": qty_avail,  # 可供卖出的可用数量 (排除已挂单锁定部分)
                "total_qty": float(qty_raw),
                "market_value": float(getattr(position, "market_value", 0.0)),
                "current_price": float(getattr(position, "current_price", 0.0)),
                "unrealized_pl": float(getattr(position, "unrealized_pl", 0.0)),
            }
        except Exception:
            return None

    def sweep_idle_cash_to_treasury(
        self, symbol: str = "SGOV", reserve_cash: float = 500.0
    ) -> Optional[Dict[str, Any]]:
        """
        将账户闲置现金买入低风险超短期国债/货币基金 (如 SGOV ETF):
        - 保留 reserve_cash (默认 $500) 基础流动性缓冲
        - 计算可买入整股数并在 Alpaca 提交买单
        """
        try:
            account_summary = self.get_account_summary()
            current_cash = account_summary["cash"]
            idle_cash = current_cash - reserve_cash

            if idle_cash < 100.0:
                logger.info(f"[Cash Sweep] 当前闲置现金 ${idle_cash:.2f} 低于单股起投阈值，无需清扫。")
                return None

            try:
                price = self.get_current_price(symbol)
            except Exception:
                price = 100.50  # 离线或基准保底估价

            shares_to_buy = int(idle_cash // price)
            if shares_to_buy <= 0:
                return None

            cost = shares_to_buy * price
            req = MarketOrderRequest(
                symbol=symbol,
                qty=shares_to_buy,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading_client.submit_order(order_data=req)
            logger.info(
                f"[Cash Sweep 成功] 闲置现金买入国债 ETF: Symbol={symbol}, Qty={shares_to_buy}, "
                f"Est Cost=${cost:.2f}, OrderID={order.id}"
            )
            return {
                "order_id": str(order.id),
                "symbol": symbol,
                "shares": shares_to_buy,
                "cost": cost,
                "remaining_cash": current_cash - cost,
            }
        except Exception as e:
            logger.warning(f"[Cash Sweep 异常] 自动买入国债 {symbol} 失败: {e}")
            return None

    def cancel_symbol_orders(self, symbol: str, side: Optional[OrderSide] = None) -> int:
        """撤销指定标的（以及可选方向）的所有未成交滞留挂单，返回成功撤销的订单数量"""
        canceled_count = 0
        try:
            open_orders = self.get_open_orders(nested=False)
            for order in open_orders:
                order_sym = getattr(order, "symbol", "")
                order_side = getattr(order, "side", None)
                if order_sym == symbol:
                    if side is None or str(order_side).upper() == str(side).upper():
                        try:
                            self.trading_client.cancel_order_by_id(order.id)
                            canceled_count += 1
                            logger.info(f"已自动撤销 {symbol} 滞留挂单: OrderID={order.id}")
                        except Exception as e:
                            logger.warning(f"撤销订单 {order.id} 失败: {e}")
        except Exception as e:
            logger.warning(f"获取并撤销 {symbol} 挂单异常: {e}")
        return canceled_count

    def release_cash_from_treasury(
        self, required_cash: float, symbol: str = "SGOV"
    ) -> float:
        """
        当交易需要现金但现金不足时，自动卖出相应份额的国债 ETF (SGOV) 释放购买力:
        - 具备【锁单自动自愈释放】：若可用为 0 但有总持仓，自动撤销旧卖单释放可用份额并重新卖出
        - 返回实际释放/卖出的估计资金额度
        """
        try:
            account_summary = self.get_account_summary()
            current_cash = account_summary["cash"]
            deficit = required_cash - current_cash
            if deficit <= 0:
                return 0.0

            pos = self.get_treasury_sweep_position(symbol=symbol)
            if not pos or pos.get("total_qty", 0) <= 0:
                logger.warning(f"[Release Cash] 现金缺口 ${deficit:.2f}，账户无任何 {symbol} 国债持仓！")
                return 0.0

            # 【智能自愈】如果可用股数为 0 但总股数 > 0，说明被历史挂单锁死，自动撤销旧挂单以释放份额
            if pos.get("qty", 0) <= 0 and pos.get("total_qty", 0) > 0:
                logger.info(f"[Release Cash] 检测到 {symbol} 全部持仓被挂单锁定，正在自动撤销历史滞留挂单以释放可用份额...")
                canceled = self.cancel_symbol_orders(symbol=symbol, side=OrderSide.SELL)
                if canceled > 0:
                    time.sleep(0.5)  # 等待 Alpaca 订单簿状态刷新
                    pos = self.get_treasury_sweep_position(symbol=symbol)

            available_qty = pos.get("qty", 0) if pos else 0
            if available_qty <= 0:
                logger.warning(f"[Release Cash] 现金缺口 ${deficit:.2f}，撤单后仍无可用 {symbol} 国债持仓可供变现！")
                return 0.0

            try:
                price = self.get_current_price(symbol)
            except Exception:
                price = pos.get("current_price") or 100.50

            shares_needed = int(-(-deficit // price))  # 向上取整
            shares_to_sell = min(int(available_qty), shares_needed)

            if shares_to_sell <= 0:
                return 0.0

            req = MarketOrderRequest(
                symbol=symbol,
                qty=shares_to_sell,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading_client.submit_order(order_data=req)
            freed_cash = shares_to_sell * price
            logger.info(
                f"[Release Cash 成功] 卖出国债 ETF 释放现金: Symbol={symbol}, Qty={shares_to_sell}, "
                f"Freed Est Cash=${freed_cash:.2f}, OrderID={order.id}"
            )
            return freed_cash
        except Exception as e:
            logger.warning(f"[Release Cash 异常] 自动变现 {symbol} 释放资金失败: {e}")
            return 0.0

# Alias for backward/forward compatibility
AlpacaExecutionClient = AlpacaGateway

