from unittest.mock import MagicMock, patch
import pytest

from core.alpaca_client import AlpacaGateway


class TestAlpacaGatewayMock:
    """AlpacaGateway 客户端方法的 Mock 单元测试类"""

    @pytest.fixture(autouse=True)
    def setup_mock(self):
        """Mock 掉 Alpaca 底层的 TradingClient 和 StockHistoricalDataClient"""
        with patch("core.alpaca_client.TradingClient") as mock_trading_cls, \
             patch("core.alpaca_client.StockHistoricalDataClient") as mock_data_cls:
            self.mock_trading_client = MagicMock()
            self.mock_data_client = MagicMock()

            mock_trading_cls.return_value = self.mock_trading_client
            mock_data_cls.return_value = self.mock_data_client

            # 实例化待测对象
            self.gateway = AlpacaGateway()
            yield

    def test_get_account(self):
        """测试获取账户信息方法 get_account"""
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_account.buying_power = "100000.00"
        self.mock_trading_client.get_account.return_value = mock_account

        account = self.gateway.get_account()

        self.mock_trading_client.get_account.assert_called_once()
        assert account.status == "ACTIVE"
        assert account.buying_power == "100000.00"

    def test_get_positions(self):
        """测试获取当前持仓方法 get_positions"""
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "10"
        self.mock_trading_client.get_all_positions.return_value = [mock_pos]

        positions = self.gateway.get_positions()

        self.mock_trading_client.get_all_positions.assert_called_once()
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"

    def test_get_open_orders(self):
        """测试获取未结委托单方法 get_open_orders"""
        mock_order = MagicMock()
        mock_order.id = "order_123"
        mock_order.symbol = "NVDA"
        self.mock_trading_client.get_orders.return_value = [mock_order]

        orders = self.gateway.get_open_orders()

        self.mock_trading_client.get_orders.assert_called_once()
        assert len(orders) == 1
        assert orders[0].id == "order_123"

    def test_get_current_price_success(self):
        """测试获取标的最新价格 (数据正常返回场景)"""
        mock_bar = MagicMock()
        mock_bar.close = 185.50

        # 模拟返回的字典 { "AAPL": [ mock_bar ] }
        self.mock_data_client.get_stock_bars.return_value = {"AAPL": [mock_bar]}

        price = self.gateway.get_current_price("AAPL")

        self.mock_data_client.get_stock_bars.assert_called_once()
        assert price == 185.50

    def test_get_current_price_not_found(self):
        """测试获取标的最新价格 (数据不存在抛出 ValueError 场景)"""
        self.mock_data_client.get_stock_bars.return_value = {}

        with pytest.raises(ValueError, match="No market data found for INVALID"):
            self.gateway.get_current_price("INVALID")

    def test_submit_bracket_order(self):
        """测试提交 Bracket 组合买单方法 submit_bracket_order"""
        mock_response_order = MagicMock()
        mock_response_order.id = "bracket_order_999"
        self.mock_trading_client.submit_order.return_value = mock_response_order

        order_res = self.gateway.submit_bracket_order(
            symbol="MSFT",
            qty=5,
            take_profit_price=420.00,
            stop_loss_price=390.00
        )

        self.mock_trading_client.submit_order.assert_called_once()
        # 校验传入的 order_data 参数属性
        call_args = self.mock_trading_client.submit_order.call_args[1]["order_data"]
        assert call_args.symbol == "MSFT"
        assert call_args.qty == 5
        assert call_args.take_profit.limit_price == 420.00
        assert call_args.stop_loss.stop_price == 390.00
        assert order_res.id == "bracket_order_999"

    def test_close_position(self):
        """测试平仓指定标的方法 close_position"""
        mock_close_res = MagicMock()
        mock_close_res.symbol = "AAPL"
        mock_close_res.status = "filled"
        self.mock_trading_client.close_position.return_value = mock_close_res

        res = self.gateway.close_position("AAPL")

        self.mock_trading_client.close_position.assert_called_once_with(symbol_or_asset_id="AAPL")
        assert res.symbol == "AAPL"
