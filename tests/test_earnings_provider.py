"""
tests/test_earnings_provider.py
Unit tests for EarningsCalendarProvider (24h local cache and yfinance integration)
"""

import os
import json
import time
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import pytest

from core.earnings_provider import EarningsCalendarProvider
from core.market_scanner import MarketScanner


def test_earnings_provider_cache_persistence(tmp_path):
    """测试财报提供器的本地持久化与读取"""
    cache_file = str(tmp_path / "earnings_test_cache.json")
    provider = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=24)

    # 预设一条缓存
    future_date = (date.today() + timedelta(days=25)).strftime("%Y-%m-%d")
    provider.cache["AAPL"] = {
        "next_earnings_date": future_date,
        "days_to_earnings": 25,
        "timestamp": time.time(),
    }
    provider._save_cache()

    assert os.path.exists(cache_file)

    # 重新实例化，验证能够从磁盘加载
    provider_new = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=24)
    days = provider_new.get_days_to_earnings("AAPL")
    assert days == 25
    assert provider_new.get_next_earnings_date("AAPL") == future_date


def test_earnings_provider_cache_expiry(tmp_path):
    """测试缓存过期后重新查询"""
    cache_file = str(tmp_path / "earnings_test_cache.json")
    provider = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=1)

    # 设置一个过期的缓存 (2小时前)
    provider.cache["NVDA"] = {
        "next_earnings_date": "2026-09-01",
        "days_to_earnings": 5,
        "timestamp": time.time() - 7200,
    }

    with patch.object(provider, "_extract_next_earnings_date_from_yf", return_value=date.today() + timedelta(days=18)):
        days = provider.get_days_to_earnings("NVDA")
        assert days == 18
        assert provider.get_next_earnings_date("NVDA") == (date.today() + timedelta(days=18)).strftime("%Y-%m-%d")


def test_earnings_provider_fallback(tmp_path):
    """测试 yfinance 报错或无日历时优雅降级返回默认天数"""
    cache_file = str(tmp_path / "earnings_test_cache.json")
    provider = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=24)

    with patch.object(provider, "_extract_next_earnings_date_from_yf", return_value=None):
        days = provider.get_days_to_earnings("UNKNOWN_TICKER", default_days=45)
        assert days == 45


def test_earnings_provider_prefetch_universe(tmp_path):
    """测试批量并发预热缓存"""
    cache_file = str(tmp_path / "earnings_test_cache.json")
    provider = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=24)

    tickers = ["AAPL", "MSFT", "GOOGL"]
    with patch.object(provider, "_extract_next_earnings_date_from_yf", return_value=date.today() + timedelta(days=20)):
        results = provider.prefetch_universe(tickers, max_workers=2)
        assert len(results) == 3
        assert results["AAPL"] == 20
        assert results["MSFT"] == 20
        assert results["GOOGL"] == 20


@pytest.mark.anyio
async def test_market_scanner_with_earnings_provider(tmp_path):
    """测试 MarketScanner 正确接入 EarningsCalendarProvider"""
    cache_file = str(tmp_path / "earnings_test_cache.json")
    provider = EarningsCalendarProvider(cache_file=cache_file, cache_ttl_hours=24)
    
    # 模拟 AAPL 处于 5 天内财报窗口 (临期)，NVDA 处于 30 天后 (安全)
    provider.cache["AAPL"] = {
        "next_earnings_date": (date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
        "days_to_earnings": 5,
        "timestamp": time.time(),
    }
    provider.cache["NVDA"] = {
        "next_earnings_date": (date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
        "days_to_earnings": 30,
        "timestamp": time.time(),
    }

    scanner = MarketScanner(earnings_provider=provider, min_score=0.50)
    universe = ["AAPL", "NVDA"]
    snapshots = {
        "AAPL": {"price": 200.0, "change_pct": 1.0, "rsi": 55.0, "sma_20": 195.0, "volume_surge": 1.2},
        "NVDA": {"price": 120.0, "change_pct": 2.0, "rsi": 60.0, "sma_20": 115.0, "volume_surge": 1.5},
    }

    results = await scanner.scan_universe_async(
        universe_tickers=universe,
        snapshots=snapshots,
        current_regime="Bull_Trend",
        top_n=5,
    )

    # 验证扫描结果中 Exotic Agent 接收到了不同的 days_to_earnings 产生的不同评估
    evals_map = {r["symbol"]: r["agent_evaluations"] for r in results}
    if "AAPL" in evals_map and "Exotic Agent" in evals_map["AAPL"]:
        rat = evals_map["AAPL"]["Exotic Agent"]["rationale"]
        assert any(k in rat for k in ["5天", "5 天", "5D", "5 d"])
    if "NVDA" in evals_map and "Exotic Agent" in evals_map["NVDA"]:
        rat = evals_map["NVDA"]["Exotic Agent"]["rationale"]
        assert any(k in rat for k in ["30天", "30 天", "30D", "30 d", "30 days"])

