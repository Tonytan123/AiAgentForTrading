# core/alpaca_client.py
import yaml
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class AlpacaGateway:
    def __init__(self):
        self.trading_client = TradingClient(
            api_key=config['alpaca']['api_key'],
            secret_key=config['alpaca']['secret_key'],
            paper=config['alpaca']['paper']
        )
        self.data_client = StockHistoricalDataClient(
            api_key=config['alpaca']['api_key'],
            secret_key=config['alpaca']['secret_key']
        )

    def get_account(self):
        return self.trading_client.get_account()

    def get_positions(self):
        return self.trading_client.get_all_positions()

    def get_open_orders(self):
        return self.trading_client.get_orders()

    def get_current_price(self, symbol: str) -> float:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=5)
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start_time,
            end=end_time
        )
        bars = self.data_client.get_stock_bars(req)
        if symbol in bars:
            return float(bars[symbol][-1].close)
        raise ValueError(f"No market data found for {symbol}")

    def submit_bracket_order(self, symbol: str, qty: int, take_profit_price: float, stop_loss_price: float):
        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=round(take_profit_price, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_loss_price, 2))
        )
        return self.trading_client.submit_order(order_data=req)

    def close_position(self, symbol: str):
        return self.trading_client.close_position(symbol_or_asset_id=symbol)