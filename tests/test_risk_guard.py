"""Unit tests for RiskGuard deterministic hard-risk control module."""

import pytest
from core.risk_guard import RiskGuard


@pytest.fixture
def default_risk_guard():
    """Fixture providing a default RiskGuard instance."""
    return RiskGuard(
        max_stock_pos_pct=0.048,
        max_option_cost_pct=0.020,
        max_total_options_pct=0.100,
        max_sector_pct=0.30,
        max_daily_drawdown_pct=0.05,
    )


def test_risk_guard_pass_normal(default_risk_guard):
    """测试正股常规合规交易：单仓、板块、日内回撤均在阈值内，应当通过校验。"""
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=4800.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.02,
        current_options_total_val=0.0,
        sector_holdings={"Technology": 15000.0, "Healthcare": 5000.0},
    )

    assert passed is True
    assert len(rejections) == 0


def test_risk_guard_daily_drawdown_breach(default_risk_guard):
    """测试日内累计回撤达到或超过 5% 触发熔断拦截。"""
    # 刚好触及 5.0% 熔断阈值
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=3000.0,
        sector="Financials",
        total_equity=100000.0,
        daily_loss_pct=0.05,
        current_options_total_val=0.0,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "触发日内回撤熔断" in rejections[0]
    assert "5.00%" in rejections[0]

    # 超过 5.0% (如 7.5%)
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=3000.0,
        sector="Financials",
        total_equity=100000.0,
        daily_loss_pct=0.075,
        current_options_total_val=0.0,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "触发日内回撤熔断" in rejections[0]


def test_risk_guard_stock_position_breach(default_risk_guard):
    """测试正股单仓下单金额占比超过 4.8% 时的拦截逻辑。"""
    # 11,000 / 100,000 = 11% > 10%
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=11000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        current_options_total_val=0.0,
        sector_holdings={"Technology": 0.0},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "正股单仓比例" in rejections[0]
    assert "11.00%" in rejections[0]


def test_risk_guard_option_cost_breach(default_risk_guard):
    """测试期权单笔权利金超过 2.0% 时的拦截逻辑。"""
    # 2,500 / 100,000 = 2.5% > 2.0%
    passed, rejections = default_risk_guard.validate(
        asset_type="OPTION",
        order_amount=2500.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        current_options_total_val=2000.0,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "期权单笔权利金" in rejections[0]


def test_risk_guard_option_total_breach(default_risk_guard):
    """测试期权总持仓敞口超过 10.0% 时的拦截逻辑。"""
    # 现有 9,000 + 新增 1,500 = 10,500 / 100,000 = 10.5% > 10.0%
    passed, rejections = default_risk_guard.validate(
        asset_type="OPTION",
        order_amount=1500.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        current_options_total_val=9000.0,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "期权总持仓敞口" in rejections[0]


def test_risk_guard_sector_concentration_breach(default_risk_guard):
    """测试板块总持仓集中度超过 30% 时的拦截逻辑。"""
    # 当前 Technology 持仓 28,000 + 新增 3,000 = 31,000 / 100,000 = 31% > 30%
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=3000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        current_options_total_val=0.0,
        sector_holdings={"Technology": 28000.0, "Financials": 5000.0},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "板块 [Technology] 总敞口 31.00%" in rejections[0]
    assert "30.00%" in rejections[0]


def test_risk_guard_multiple_violations(default_risk_guard):
    """测试同时违反多项硬风控规则（日内回撤、单仓、板块敞口全部超限）。"""
    # 日内浮亏 6% >= 5%, 正股单仓 6,000 (6%) > 4.8%, 板块总额 26,000 + 6,000 = 32% > 30%
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=6000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.06,
        current_options_total_val=0.0,
        sector_holdings={"Technology": 26000.0},
    )

    assert passed is False
    assert len(rejections) == 3
    assert any("触发日内回撤熔断" in r for r in rejections)
    assert any("正股单仓比例" in r for r in rejections)
    assert any("板块 [Technology]" in r for r in rejections)


def test_risk_guard_boundary_conditions(default_risk_guard):
    """测试边界值临界状态：恰好等于上限阈值时应当通过。"""
    # 1. 恰好正股单仓 4.8% (4,800 / 100,000)
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=4800.0,
        sector="Healthcare",
        total_equity=100000.0,
        daily_loss_pct=0.0,
        current_options_total_val=0.0,
        sector_holdings={},
    )
    assert passed is True
    assert len(rejections) == 0

    # 2. 恰好期权单笔 2.0% (2,000 / 100,000) 且总占用 10.0% (8,000 + 2,000 = 10,000 / 100,000)
    passed, rejections = default_risk_guard.validate(
        asset_type="OPTION",
        order_amount=2000.0,
        sector="Healthcare",
        total_equity=100000.0,
        daily_loss_pct=0.0,
        current_options_total_val=8000.0,
        sector_holdings={},
    )
    assert passed is True
    assert len(rejections) == 0

    # 3. 恰好板块 30.0% (现有 26,000 + 新增 4,000 = 30,000 / 100,000)
    passed, rejections = default_risk_guard.validate(
        asset_type="EQUITY",
        order_amount=4000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.0,
        current_options_total_val=0.0,
        sector_holdings={"Technology": 26000.0},
    )
    assert passed is True
    assert len(rejections) == 0


def test_risk_guard_positional_backward_compatibility(default_risk_guard):
    """测试历史位置参数调用向后兼容性。"""
    passed, rejections = default_risk_guard.validate(
        4000.0,
        "Technology",
        100000.0,
        0.01,
        {"Technology": 10000.0},
    )
    assert passed is True
    assert len(rejections) == 0
