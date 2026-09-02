"""Unit and integration test module for AlpacaGateway."""

from unittest.mock import MagicMock, patch
from alpaca.trading.enums import OrderStatus
import pytest
from core.alpaca_client import AlpacaGateway


class TestAlpacaGatewayReal:
    """实际调用 Alpaca Paper Trading API 的集成测试类，测试并详细打印抓取到的数据"""

    @pytest.fixture
    def gateway(self):
        """Fixture returning an instance of AlpacaGateway."""
        return AlpacaGateway()

    def test_real_get_account(self, gateway):
        """测试获取 Alpaca 账户信息并打印"""
        account = gateway.get_account()

        print("\n" + "=" * 60)
        print("【Alpaca 账户信息数据详情】")
        print("=" * 60)
        print(f"账户 ID         : {account.id}")
        print(f"账户状态        : {account.status}")
        print(f"货币币种        : {account.currency}")
        print(f"总净资产 (Equity): ${float(account.equity):,.2f}")
        print(f"现金余额 (Cash) : ${float(account.cash):,.2f}")
        print(f"购买力 (Buying) : ${float(account.buying_power):,.2f}")
        print(f"是否受限交易    : {account.trading_blocked}")
        print("=" * 60)

        assert account is not None
        assert account.status == "ACTIVE"
        assert float(account.equity) >= 0

    def test_real_get_positions(self, gateway):
        """测试获取当前持仓列表并打印"""
        positions = gateway.get_positions()

        print("\n" + "=" * 60)
        print("【Alpaca 当前持仓数据详情】")
        print("=" * 60)
        if positions:
            for p in positions:
                pl_pct = float(p.unrealized_plpc) * 100
                print(
                    f"标的: {p.symbol:<6} | 数量: {p.qty:<6} | "
                    f"均价: ${float(p.avg_entry_price):.2f} | "
                    f"现价: ${float(p.current_price):.2f} | "
                    f"浮动盈亏: ${float(p.unrealized_pl):.2f} ({pl_pct:.2f}%)"
                )
        else:
            print("当前暂无任何持仓 (No Open Positions)")
        print("=" * 60)

        assert isinstance(positions, list)

    def test_real_get_open_orders(self, gateway):
        """测试获取当前活动挂单并打印"""
        orders = gateway.get_open_orders()

        print("\n" + "=" * 60)
        print("【Alpaca 活动挂单数据详情】")
        print("=" * 60)
        if orders:
            for o in orders:
                print(
                    f"订单 ID: {o.id} | 标的: {o.symbol} | 方向: {o.side} | "
                    f"数量: {o.qty} | 状态: {o.status} | 类型: {o.order_type}"
                )
        else:
            print("当前暂无未结挂单 (No Open Orders)")
        print("=" * 60)

        assert isinstance(orders, list)

    def test_real_get_current_price(self, gateway):
        """测试拉取指定标的 (AAPL & SPY) 的最新市场价格并打印"""
        test_symbols = ["AAPL", "SPY"]

        print("\n" + "=" * 60)
        print("【Alpaca 实时标的行情价格详情】")
        print("=" * 60)
        for sym in test_symbols:
            price = gateway.get_current_price(sym)
            print(f"标的代码: {sym:<6} | 最新日线收盘价: ${price:.2f}")
            assert price > 0, f"{sym} 价格必须大于 0"
        print("=" * 60)


class TestAlpacaGatewayMock:
    """Mock 单元测试类，离线模拟测试下单与平仓逻辑"""

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_submit_bracket_order(self, _mock_data_client, mock_trading_client):
        """测试提交 Bracket Order (带止盈止损的包围单)"""
        mock_order_response = MagicMock()
        mock_order_response.id = "mock-order-id-12345"
        mock_order_response.symbol = "AAPL"
        mock_order_response.qty = 10
        mock_order_response.status = OrderStatus.ACCEPTED

        mock_instance = MagicMock()
        mock_instance.submit_order.return_value = mock_order_response
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        res = gateway.submit_bracket_order(
            symbol="AAPL",
            qty=10,
            take_profit_price=230.50,
            stop_loss_price=210.00,
        )

        mock_instance.submit_order.assert_called_once()
        assert res.id == "mock-order-id-12345"
        assert res.symbol == "AAPL"

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_close_position(self, _mock_data_client, mock_trading_client):
        """测试平仓指定标的"""
        mock_instance = MagicMock()
        mock_instance.close_position.return_value = {
            "symbol": "AAPL",
            "status": "closed",
        }
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        res = gateway.close_position("AAPL")

        mock_instance.close_position.assert_called_once_with(symbol_or_asset_id="AAPL")
        assert res["symbol"] == "AAPL"

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_sweep_idle_cash_to_treasury(self, mock_data_client, mock_trading_client):
        """测试闲置现金自动清扫买入国债 ETF (SGOV)"""
        mock_acc = MagicMock()
        mock_acc.equity = "100000.0"
        mock_acc.buying_power = "200000.0"
        mock_acc.cash = "5500.0"
        mock_acc.last_equity = "100000.0"

        mock_instance = MagicMock()
        mock_instance.get_account.return_value = mock_acc

        mock_order = MagicMock()
        mock_order.id = "sweep-order-001"
        mock_instance.submit_order.return_value = mock_order
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        # Mock 获取当前 SGOV 价格为 100.0
        gateway.get_current_price = MagicMock(return_value=100.0)

        # 现金 5500，保留 500，闲置 5000 -> 买入 50 股 SGOV
        res = gateway.sweep_idle_cash_to_treasury(symbol="SGOV", reserve_cash=500.0)
        assert res is not None
        assert res["shares"] == 50
        assert res["cost"] == 5000.0
        assert res["symbol"] == "SGOV"
        mock_instance.submit_order.assert_called_once()

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_release_cash_from_treasury(self, mock_data_client, mock_trading_client):
        """测试资金不足时自动卖出 SGOV 释放现金"""
        mock_acc = MagicMock()
        mock_acc.equity = "100000.0"
        mock_acc.buying_power = "200000.0"
        mock_acc.cash = "1000.0"
        mock_acc.last_equity = "100000.0"

        mock_pos = MagicMock()
        mock_pos.symbol = "SGOV"
        mock_pos.qty = "100"
        mock_pos.market_value = "10050.0"
        mock_pos.current_price = "100.50"
        mock_pos.unrealized_pl = "10.0"

        mock_instance = MagicMock()
        mock_instance.get_account.return_value = mock_acc
        mock_instance.get_open_position.return_value = mock_pos

        mock_order = MagicMock()
        mock_order.id = "release-order-001"
        mock_instance.submit_order.return_value = mock_order
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        gateway.get_current_price = MagicMock(return_value=100.0)

        # 需要 3000 现金，当前只有 1000 -> 缺口 2000 -> 卖出 20 股 SGOV
        freed = gateway.release_cash_from_treasury(required_cash=3000.0, symbol="SGOV")
        assert freed == 2000.0
        mock_instance.submit_order.assert_called_once()

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_get_positions(self, _mock_data_client, mock_trading_client):
        """测试获取持仓列表的 mock 测试"""
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "50"
        mock_pos.market_value = "11625.00"

        mock_instance = MagicMock()
        mock_instance.get_all_positions.return_value = [mock_pos]
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        positions = gateway.get_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"
        mock_instance.get_all_positions.assert_called_once()

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_get_open_orders(self, _mock_data_client, mock_trading_client):
        """测试获取未成交订单列表的 mock 测试"""
        mock_order = MagicMock()
        mock_order.id = "ord-mock-001"
        mock_order.symbol = "MSFT"
        mock_order.status = "accepted"

        mock_instance = MagicMock()
        mock_instance.get_orders.return_value = [mock_order]
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        orders = gateway.get_open_orders()
        assert len(orders) == 1
        assert orders[0].symbol == "MSFT"
        mock_instance.get_orders.assert_called_once()

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_place_option_limit_order(self, _mock_data_client, mock_trading_client):
        """测试期权限价单提交的 mock 测试"""
        mock_order = MagicMock()
        mock_order.id = "opt-mock-001"

        mock_instance = MagicMock()
        mock_instance.submit_order.return_value = mock_order
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        order_id = gateway.place_option_limit_order(
            contract_symbol="V260918C00387000",
            contracts=1,
            limit_price=13.28,
        )
        assert order_id == "opt-mock-001"
        mock_instance.submit_order.assert_called_once()

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_cancel_symbol_orders(self, _mock_data_client, mock_trading_client):
        """测试按标的批量撤单"""
        mock_order1 = MagicMock()
        mock_order1.id = "ord-sgov-001"
        mock_order1.symbol = "SGOV"
        mock_order1.side = "sell"

        mock_order2 = MagicMock()
        mock_order2.id = "ord-aapl-002"
        mock_order2.symbol = "AAPL"
        mock_order2.side = "buy"

        mock_instance = MagicMock()
        mock_instance.get_orders.return_value = [mock_order1, mock_order2]
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        canceled = gateway.cancel_symbol_orders(symbol="SGOV")
        assert canceled == 1
        mock_instance.cancel_order_by_id.assert_called_once_with("ord-sgov-001")

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_get_option_contracts(self, _mock_data_client, mock_trading_client):
        """测试查询期权合约链列表"""
        mock_contract = MagicMock()
        mock_contract.symbol = "AAPL260918C00330000"
        mock_contract.strike_price = "330.00"
        mock_contract.expiration_date = "2026-09-18"
        mock_contract.type = "call"
        mock_contract.tradable = True

        mock_res = MagicMock()
        mock_res.option_contracts = [mock_contract]

        mock_instance = MagicMock()
        mock_instance.get_option_contracts.return_value = mock_res
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        contracts = gateway.get_option_contracts(underlying_symbol="AAPL")
        assert len(contracts) == 1
        assert contracts[0].symbol == "AAPL260918C00330000"

    @patch("core.alpaca_client.TradingClient")
    @patch("core.alpaca_client.StockHistoricalDataClient")
    def test_mock_get_best_option_contract(self, _mock_data_client, mock_trading_client):
        """测试根据目标行权价与 DTE 智能挑选最优期权合约"""
        import datetime
        today = datetime.date.today()
        exp_date_str = (today + datetime.timedelta(days=21)).strftime("%Y-%m-%d")

        c1 = MagicMock()
        c1.symbol = "AAPL260918C00320000"
        c1.strike_price = "320.00"
        c1.expiration_date = exp_date_str
        c1.type = "call"
        c1.tradable = True
        c1.close_price = "12.50"

        c2 = MagicMock()
        c2.symbol = "AAPL260918C00330000"
        c2.strike_price = "330.00"
        c2.expiration_date = exp_date_str
        c2.type = "call"
        c2.tradable = True
        c2.close_price = "8.20"

        mock_res = MagicMock()
        mock_res.option_contracts = [c1, c2]

        mock_instance = MagicMock()
        mock_instance.get_option_contracts.return_value = mock_res
        mock_trading_client.return_value = mock_instance

        gateway = AlpacaGateway()
        # 目标行权价 331.3，最优匹配应该选 $330 的 c2 (距离只有 1.3)
        best = gateway.get_best_option_contract(
            underlying_symbol="AAPL",
            target_strike=331.3,
            option_type="call"
        )
        assert best is not None
        assert best["contract_symbol"] == "AAPL260918C00330000"
        assert best["strike_price"] == 330.00
        assert best["dte"] == 21
        assert best["option_type"] == "Call"



