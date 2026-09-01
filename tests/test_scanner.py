"""Unit tests for core.market_scanner module."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from rich.table import Table
from core.market_scanner import MarketScanner, extract_underlying_symbol
from cli.terminal_ui import render_scanner_results_table, print_scanner_results


def test_extract_underlying_symbol():
    """测试正股与期权代码的基础标的提取"""
    assert extract_underlying_symbol("AAPL") == "AAPL"
    assert extract_underlying_symbol("aapl") == "AAPL"
    assert extract_underlying_symbol("NVDA260918C00130000") == "NVDA"
    assert extract_underlying_symbol("TSLA261016P00250000") == "TSLA"
    assert extract_underlying_symbol("") == ""


def test_market_scanner_empty():
    """测试空快照或无标的时的扫盘结果"""
    scanner = MarketScanner()
    results = scanner.scan_universe([], {})
    assert results == []


@pytest.mark.anyio
async def test_market_scanner_async_consensus_debate():
    """测试异步调用 ConsensusEngine 真实协商打分流程"""
    scanner = MarketScanner(min_score=0.70)
    universe = ["NVDA", "AAPL"]
    snapshots = {
        "NVDA": {"price": 220.0, "change_pct": 3.5, "rsi": 58.0, "sma_20": 210.0, "volume_surge": 1.8},
        "AAPL": {"price": 315.0, "change_pct": 1.2, "rsi": 52.0, "sma_20": 310.0, "volume_surge": 1.1},
    }

    results = await scanner.scan_universe_async(
        universe_tickers=universe,
        snapshots=snapshots,
        current_regime="Bull_Trend",
        top_n=5,
    )

    assert len(results) >= 1
    top = results[0]
    assert top["consensus_score"] >= 0.70
    assert "agent_evaluations" in top


def test_market_scanner_held_and_order_distinction():
    """测试已持仓标的与挂单中标的在扫盘结果中的区分标记"""
    scanner = MarketScanner(min_score=0.60)
    universe = ["AAPL", "AMZN", "MSFT", "NVDA"]
    snapshots = {
        "AAPL": {"price": 315.0, "change_pct": 1.5, "rsi": 55.0, "sma_20": 300.0, "volume_surge": 1.5},
        "AMZN": {"price": 260.0, "change_pct": 1.5, "rsi": 55.0, "sma_20": 250.0, "volume_surge": 1.5},
        "MSFT": {"price": 505.0, "change_pct": 1.5, "rsi": 55.0, "sma_20": 495.0, "volume_surge": 1.5},
        "NVDA": {"price": 220.0, "change_pct": 1.5, "rsi": 55.0, "sma_20": 210.0, "volume_surge": 1.5},
    }

    mock_positions = [{"symbol": "AAPL", "qty": 30}, {"symbol": "MSFT", "qty": 9}]
    mock_orders = [{"symbol": "AMZN", "qty": 18}, {"symbol": "MSFT", "qty": 9}]

    results = scanner.scan_universe(
        universe_tickers=universe,
        snapshots=snapshots,
        current_regime="Bull_Trend",
        positions=mock_positions,
        orders=mock_orders,
        top_n=10,
    )

    res_map = {r["symbol"]: r for r in results}
    assert res_map["AAPL"]["status_tag"] == "HELD"
    assert res_map["AMZN"]["status_tag"] == "ORDERED"
    assert res_map["MSFT"]["status_tag"] == "HELD_ORDER"
    assert res_map["NVDA"]["status_tag"] == "NEW"


def test_market_scanner_regime_adaptation():
    """测试不同宏观体制对资产类型与得分的动态自适应"""
    scanner = MarketScanner(min_score=0.60)
    snapshots = {
        "MSFT": {
            "price": 500.0,
            "change_pct": 2.5,
            "rsi": 62.0,
            "sma_20": 490.0,
            "volume_surge": 1.5,
        }
    }

    # 震荡市推荐期权牛市价差
    results_neutral = scanner.scan_universe(
        universe_tickers=["MSFT"],
        snapshots=snapshots,
        current_regime="Neutral_Range",
    )
    assert len(results_neutral) == 1
    assert results_neutral[0]["recommended_asset"] == "BULL_CALL_SPREAD"

    # 恐慌市直接压低评分淘汰
    results_panic = scanner.scan_universe(
        universe_tickers=["MSFT"],
        snapshots=snapshots,
        current_regime="Panic_Crisis",
    )
    assert len(results_panic) == 0


def test_render_scanner_results_table():
    """测试扫盘结果表格富文本渲染与无异常打印"""
    mock_results = [
        {
            "symbol": "NVDA",
            "sector": "Information Technology",
            "score": 0.88,
            "consensus_score": 0.88,
            "price": 220.80,
            "status_tag": "NEW",
            "status_display": "新机会",
            "recommended_asset": "EQUITY",
            "asset_display": "正股",
            "take_profit_price": 238.46,
            "stop_loss_price": 211.97,
            "risk_reward_ratio": 2.0,
            "rationale": "站上SMA20 | 日内+1.5% | RSI=58健康 | 放量1.8x",
        },
        {
            "symbol": "AAPL",
            "sector": "Information Technology",
            "score": 0.80,
            "consensus_score": 0.80,
            "price": 315.00,
            "status_tag": "HELD",
            "status_display": "已持仓",
            "recommended_asset": "EQUITY",
            "asset_display": "正股",
            "take_profit_price": 340.20,
            "stop_loss_price": 302.40,
            "risk_reward_ratio": 2.0,
            "rationale": "站上SMA20 | 已持仓",
        },
    ]

    table = render_scanner_results_table(mock_results, current_regime="Bull_Trend")
    assert isinstance(table, Table)
    assert len(table.columns) == 11

    empty_table = render_scanner_results_table([], current_regime="Panic_Crisis")
    assert isinstance(empty_table, Table)

    print_scanner_results(mock_results)
