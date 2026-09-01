"""Unit tests for cli.terminal_ui module."""

from unittest.mock import MagicMock
from rich.table import Table
from cli.terminal_ui import (
    render_positions_table,
    render_open_orders_table,
    print_positions_table,
    print_open_orders_table,
    print_portfolio_dashboard,
)


def test_render_positions_table_empty():
    """测试当持仓为空时的表格渲染"""
    table = render_positions_table([])
    assert isinstance(table, Table)
    symbols = table.columns[1]._cells
    assert len(symbols) == 1
    assert "暂无持仓" in symbols[0]


def test_render_positions_table_with_mock_data():
    """测试包含正股、期权和国债 ETF 数据的持仓表格渲染"""
    mock_positions = [
        {
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "side": "long",
            "qty": 50,
            "avg_entry_price": 220.00,
            "current_price": 232.50,
            "market_value": 11625.00,
            "cost_basis": 11000.00,
            "unrealized_pl": 625.00,
            "unrealized_plpc": 0.0568,
            "change_today": 0.0145,
        },
        {
            "symbol": "NVDA260918C00130000",
            "asset_class": "us_option",
            "side": "long",
            "qty": 2,
            "avg_entry_price": 8.50,
            "current_price": 10.20,
            "market_value": 2040.00,
            "cost_basis": 1700.00,
            "unrealized_pl": 340.00,
            "unrealized_plpc": 0.2000,
            "change_today": 0.0850,
        },
        {
            "symbol": "SGOV",
            "asset_class": "us_equity",
            "side": "long",
            "qty": 100,
            "avg_entry_price": 100.45,
            "current_price": 100.52,
            "market_value": 10052.00,
            "cost_basis": 10045.00,
            "unrealized_pl": 7.00,
            "unrealized_plpc": 0.0007,
            "change_today": 0.0001,
        },
    ]

    table = render_positions_table(mock_positions)
    assert isinstance(table, Table)
    assert len(table.columns) == 11
    symbols = table.columns[1]._cells
    assert symbols == ["AAPL", "NVDA260918C00130000", "SGOV"]
    asset_types = table.columns[2]._cells
    assert "正股" in asset_types[0]
    assert "期权" in asset_types[1]
    assert "国债ETF" in asset_types[2]


def test_render_positions_table_with_objects():
    """测试传入对象类型而非字典时的兼容性"""
    pos_obj = MagicMock()
    pos_obj.symbol = "MSFT"
    pos_obj.asset_class = "us_equity"
    pos_obj.side = "long"
    pos_obj.qty = "10"
    pos_obj.avg_entry_price = "400.00"
    pos_obj.current_price = "420.00"
    pos_obj.market_value = "4200.00"
    pos_obj.cost_basis = "4000.00"
    pos_obj.unrealized_pl = "200.00"
    pos_obj.unrealized_plpc = "0.05"
    pos_obj.change_today = "0.02"

    table = render_positions_table([pos_obj])
    assert isinstance(table, Table)
    assert table.columns[1]._cells == ["MSFT"]
    assert table.columns[7]._cells == ["$4,200.00"]


def test_render_open_orders_table_empty():
    """测试未成交订单为空时的表格渲染"""
    table = render_open_orders_table([])
    assert isinstance(table, Table)
    symbols = table.columns[2]._cells
    assert len(symbols) == 1
    assert "暂无未成交订单" in symbols[0]


def test_render_open_orders_table_with_data():
    """测试各类订单（限价单、止损限价单、Bracket 单）的表格渲染"""
    mock_orders = [
        {
            "id": "ord-883a91b2c4e5",
            "symbol": "MSFT",
            "side": "buy",
            "order_type": "limit",
            "qty": 20,
            "filled_qty": 0,
            "limit_price": 415.00,
            "stop_price": None,
            "order_class": "bracket",
            "status": "accepted",
            "time_in_force": "day",
            "submitted_at": "2026-09-01T14:30:00Z",
        },
        {
            "id": "ord-12ff09e871cd",
            "symbol": "TSLA",
            "side": "sell",
            "order_type": "stop_limit",
            "qty": 10,
            "filled_qty": 2,
            "limit_price": 210.00,
            "stop_price": 208.50,
            "order_class": "simple",
            "status": "partially_filled",
            "time_in_force": "gtc",
            "submitted_at": "2026-09-01T15:10:22Z",
        },
    ]

    table = render_open_orders_table(mock_orders)
    assert isinstance(table, Table)
    assert len(table.columns) == 11
    symbols = table.columns[2]._cells
    assert symbols == ["MSFT", "TSLA"]
    order_types = table.columns[4]._cells
    assert order_types == ["LIMIT", "STOP_LIMIT"]
    progress = table.columns[5]._cells
    assert progress == ["0/20", "2/10"]


def test_render_open_orders_table_with_objects():
    """测试未成交订单对象形式的兼容性"""
    ord_obj = MagicMock()
    ord_obj.id = "ord-uuid-12345678"
    ord_obj.symbol = "AAPL"
    ord_obj.side = "buy"
    ord_obj.order_type = "market"
    ord_obj.qty = "15"
    ord_obj.filled_qty = "0"
    ord_obj.limit_price = None
    ord_obj.stop_price = None
    ord_obj.order_class = "simple"
    ord_obj.status = "new"
    ord_obj.time_in_force = "day"
    ord_obj.submitted_at = "2026-09-01T10:00:00Z"

    table = render_open_orders_table([ord_obj])
    assert isinstance(table, Table)
    assert table.columns[2]._cells == ["AAPL"]
    assert "ord-uuid" in table.columns[1]._cells[0]


def test_print_dashboard_functions():
    """测试 print 封装函数的无异常调用"""
    print_positions_table([])
    print_open_orders_table([])
    print_portfolio_dashboard([], [])
