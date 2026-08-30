import logging
import yaml
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestBarRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import (
    MarketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)

logger = logging.getLogger(__name__)

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class AlpacaGateway:
    """Gateway interface for interacting with Alpaca Trading & Market Data APIs."""

    def __init__(self, api_key: str = None, secret_key: str = None, paper: bool = None):
        key = api_key or config.get("alpaca", {}).get("api_key")
        secret = secret_key or config.get("alpaca", {}).get("secret_key")
        is_paper = paper if paper is not None else config.get("alpaca", {}).get("paper", True)

        self.trading_client = TradingClient(
            api_key=key,
            secret_key=secret,
            paper=is_paper,
        )
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

    def get_account_summary(self):
        account = self.trading_client.get_account()
        return {
            "total_equity": float(account.equity),  # 总权益
            "buying_power": float(account.buying_power),  # 购买力
            "cash": float(account.cash),  # 现金
            "day_pnl_pct": (float(account.equity) - float(account.last_equity)) / float(account.last_equity) if float(account.last_equity) else 0.0 #当日盈亏百分比
        }

    def place_bracket_oco_order(self, ticker: str, shares: int, take_profit_price: float, stop_loss_price: float):
        """提交 OCO (市价入场 + GTC 止盈止损)"""
        req = MarketOrderRequest(
            symbol=ticker,  # 股票代码
            qty=shares,  # 股数
            side=OrderSide.BUY,  # 买入
            time_in_force=TimeInForce.DAY,  # 日间委托
            order_class=OrderClass.BRACKET,  # 括号订单
            take_profit=TakeProfitRequest(limit_price=take_profit_price),  # 止盈价
            stop_loss=StopLossRequest(stop_price=stop_loss_price)  # 止损价
        )
        order = self.trading_client.submit_order(order_data=req)
        logger.info(f"Bracket OCO 下单成功: Symbol={ticker}, ID={order.id}")
        return str(order.id)


# Alias for backward/forward compatibility
AlpacaExecutionClient = AlpacaGateway