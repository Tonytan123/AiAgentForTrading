from langsmith._openapi_client.types import run_select_field
from typing import Any, Dict, Optional
import logging
import yaml
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
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

    def get_positions(self):
        """Retrieve all currently held open positions."""
        return self.trading_client.get_all_positions()

    def get_open_orders(self):
        """Retrieve all currently active open orders."""
        return self.trading_client.get_orders()

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

    def close_position(self, symbol: str):
        """Liquidate and close an open position for a given symbol."""
        return self.trading_client.close_position(symbol_or_asset_id=symbol)


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
            time_in_force=TimeInForce.DAY, #设置订单的有效期限为当日有效
            limit_price=limit_price #期权订单的限价（买入期权）或止损价（卖出期权）
        )
        order = self.client.submit_order(order_data=req)
        logger.info(f"期权限价单提交成功: Contract={contract_symbol}, Qty={contracts}, Price=${limit_price:.2f}, OrderID={order.id}")
        return str(order.id)

# Alias for backward/forward compatibility
AlpacaExecutionClient = AlpacaGateway
