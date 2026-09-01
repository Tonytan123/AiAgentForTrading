"""
tests/test_critic_agent.py
Unit tests for CriticAgent audit logic (EQUITY and OPTION hybrid proposals)
"""

import pytest
from core.agents.critic_agent import CriticAgent


def test_critic_audit_equity_valid():
    """测试合规的正股提案通过审查"""
    critic = CriticAgent(config_path="config/investment_memo.yaml")
    proposal = {
        "proposal_id": "PROP-20260901-NVDA-EQ-01",
        "ticker": "NVDA",
        "action": "BUY",
        "asset_type": "EQUITY",
        "position_pct": 0.045,
        "leverage": 1.0,
        "suggested_shares": 20,
        "take_profit_price": 235.0,
        "stop_loss_price": 208.0,
        "consensus_score": 0.85,
    }
    passed, violations = critic.audit(
        proposal=proposal,
        sp500_whitelist=["NVDA", "AAPL"],
        days_to_earnings=25,
        asset_type="EQUITY",
    )
    assert passed is True
    assert len(violations) == 0


def test_critic_audit_option_valid():
    """测试合规的期权提案（无 suggested_shares 但有 suggested_contracts）通过审查"""
    critic = CriticAgent(config_path="config/investment_memo.yaml")
    proposal = {
        "proposal_id": "PROP-20260901-V-OPT-01",
        "ticker": "V",
        "underlying_ticker": "V",
        "action": "BUY_TO_OPEN",
        "asset_type": "OPTION",
        "cost_pct": 0.0133,
        "dte": 18,
        "suggested_contracts": 1,
        "suggested_shares": None,
        "take_profit_price": 19.92,
        "stop_loss_price": 9.30,
        "consensus_score": 0.85,
    }
    passed, violations = critic.audit(
        proposal=proposal,
        sp500_whitelist=["V", "AAPL"],
        days_to_earnings=57,
        asset_type="OPTION",
    )
    assert passed is True
    assert len(violations) == 0


def test_critic_audit_earnings_blackout():
    """测试 7 天内二元财报窗口被拦截"""
    critic = CriticAgent(config_path="config/investment_memo.yaml")
    proposal = {
        "proposal_id": "PROP-20260901-AAPL-EQ-01",
        "ticker": "AAPL",
        "action": "BUY",
        "asset_type": "EQUITY",
        "suggested_shares": 10,
        "position_pct": 0.03,
        "take_profit_price": 340.0,
        "stop_loss_price": 305.0,
        "consensus_score": 0.80,
    }
    passed, violations = critic.audit(
        proposal=proposal,
        sp500_whitelist=["AAPL"],
        days_to_earnings=5,  # <= 7 天
        asset_type="EQUITY",
    )
    assert passed is False
    assert any("7 天内二元事件" in v for v in violations)
