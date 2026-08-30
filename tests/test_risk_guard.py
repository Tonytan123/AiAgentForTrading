"""Unit tests for RiskGuard deterministic hard-risk control module."""

import pytest
from core.risk_guard import RiskGuard


@pytest.fixture
def default_risk_guard():
    """Fixture providing a default RiskGuard instance."""
    return RiskGuard(
        max_position_pct=0.10,
        max_sector_pct=0.30,
        max_daily_drawdown_pct=0.09,
    )


def test_risk_guard_pass_normal(default_risk_guard):
    """测试常规合规交易：单仓、板块、日内回撤均在阈值内，应当通过校验。"""
    passed, rejections = default_risk_guard.validate(
        order_amount=4800.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.02,
        sector_holdings={"Technology": 15000.0, "Healthcare": 5000.0},
    )

    assert passed is True
    assert len(rejections) == 0


def test_risk_guard_daily_drawdown_breach(default_risk_guard):
    """测试日内累计回撤达到或超过 9% 触发熔断拦截。"""
    # 刚好触及 9.0% 熔断阈值
    passed, rejections = default_risk_guard.validate(
        order_amount=3000.0,
        sector="Financials",
        total_equity=100000.0,
        daily_loss_pct=0.09,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "触发当日回撤熔断" in rejections[0]
    assert "9.00%" in rejections[0]

    # 超过 9.0% (如 12.5%)
    passed, rejections = default_risk_guard.validate(
        order_amount=3000.0,
        sector="Financials",
        total_equity=100000.0,
        daily_loss_pct=0.125,
        sector_holdings={},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "触发当日回撤熔断" in rejections[0]


def test_risk_guard_single_position_breach(default_risk_guard):
    """测试单仓下单金额占比超过 10% 时的拦截逻辑。"""
    # 12,000 / 100,000 = 12% > 10%
    passed, rejections = default_risk_guard.validate(
        order_amount=12000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        sector_holdings={"Technology": 0.0},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "单仓比例" in rejections[0]
    assert "12.00%" in rejections[0]


def test_risk_guard_sector_concentration_breach(default_risk_guard):
    """测试板块总持仓集中度超过 30% 时的拦截逻辑。"""
    # 当前 Technology 持仓 26,000 + 新增 5,000 = 31,000 / 100,000 = 31% > 30%
    passed, rejections = default_risk_guard.validate(
        order_amount=5000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.01,
        sector_holdings={"Technology": 26000.0, "Financials": 10000.0},
    )

    assert passed is False
    assert len(rejections) == 1
    assert "板块 [Technology] 敞口将达 31.00%" in rejections[0]
    assert "30.00%" in rejections[0]


def test_risk_guard_multiple_violations(default_risk_guard):
    """测试同时违反多项硬风控规则（日内回撤、单仓、板块敞口全部超限）。"""
    # 日内浮亏 10% >= 9%, 单仓 15,000 (15%) > 10%, 板块总额 20,000 + 15,000 = 35% > 30%
    passed, rejections = default_risk_guard.validate(
        order_amount=15000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.10,
        sector_holdings={"Technology": 20000.0},
    )

    assert passed is False
    assert len(rejections) == 3
    assert any("触发当日回撤熔断" in r for r in rejections)
    assert any("单仓比例" in r for r in rejections)
    assert any("板块 [Technology]" in r for r in rejections)


def test_risk_guard_boundary_conditions(default_risk_guard):
    """测试边界值临界状态：恰好等于上限阈值时应当通过。"""
    # 1. 恰好单仓 10.0% (10,000 / 100,000)
    passed, rejections = default_risk_guard.validate(
        order_amount=10000.0,
        sector="Healthcare",
        total_equity=100000.0,
        daily_loss_pct=0.0,
        sector_holdings={},
    )
    assert passed is True
    assert len(rejections) == 0

    # 2. 恰好板块 30.0% (现有 20,000 + 新增 10,000 = 30,000 / 100,000)
    passed, rejections = default_risk_guard.validate(
        order_amount=10000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.0,
        sector_holdings={"Technology": 20000.0},
    )
    assert passed is True
    assert len(rejections) == 0

    # 3. 恰好日内回撤低于 9.0% (例如 8.99%)
    passed, rejections = default_risk_guard.validate(
        order_amount=5000.0,
        sector="Technology",
        total_equity=100000.0,
        daily_loss_pct=0.0899,
        sector_holdings={},
    )
    assert passed is True
    assert len(rejections) == 0


def test_risk_guard_custom_thresholds():
    """测试自定义更加严格或宽松的阈值参数。"""
    custom_guard = RiskGuard(
        max_position_pct=0.05,  # 单仓上限 5%
        max_sector_pct=0.20,  # 板块上限 20%
        max_daily_drawdown_pct=0.04,  # 日内回撤上限 4%
    )

    # 下单 6% (6,000 / 100,000) 在默认 10% 下可通过，在自定义 5% 下应被拦截
    passed, rejections = custom_guard.validate(
        order_amount=6000.0,
        sector="Consumer Discretionary",
        total_equity=100000.0,
        daily_loss_pct=0.02,
        sector_holdings={},
    )
    assert passed is False
    assert len(rejections) == 1
    assert "单仓比例 6.00% 超过硬风控阈值 5.00%" in rejections[0]
