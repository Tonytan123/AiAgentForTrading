"""
core/earnings_provider.py
美股财报日历获取与 24 小时本地持久化缓存提供器 (Earnings Calendar Provider)
基于 yfinance 与本地 JSON 缓存，提供精准的财报发布日计算与二元财报窗口 (Blackout Days) 避让支持。
"""

import os
import json
import time
import logging
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class EarningsCalendarProvider:
    """
    财报日历数据提供器:
    - 查询美股标的下一次财报发布日期及距离今天的天数 (days_to_earnings)
    - 具备内存 + 磁盘 JSON 文件的双层 24 小时 (可配置 TTL) 持久化缓存
    - 支持多线程批量预加载 (prefetch)，大幅降低扫盘时的延迟
    - 异常与无财报数据自动安全降级为兜底值 (默认 30 天)
    """

    def __init__(
        self,
        cache_file: str = "config/earnings_cache.json",
        cache_ttl_hours: int = 24,
    ):
        self.cache_file = cache_file
        self.cache_ttl_seconds = max(60, cache_ttl_hours * 3600)
        self.cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """从本地磁盘读取持久化缓存"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logger.warning(f"读取财报日历缓存失败: {e}，将初始化为空缓存")
        return {}

    def _save_cache(self) -> None:
        """持久化保存缓存到本地磁盘"""
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.cache_file)), exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"写入财报日历缓存文件失败: {e}")

    def _extract_next_earnings_date_from_yf(self, ticker: str) -> Optional[date]:
        """通过 yfinance 查询标的下一次财报日期 (尝试 calendar 与 get_earnings_dates)"""
        today = date.today()
        try:
            t = yf.Ticker(ticker)

            # 1. 优先尝试 t.calendar
            cal = getattr(t, "calendar", None)
            if cal is not None:
                if isinstance(cal, dict) and "Earnings Date" in cal:
                    dates = cal["Earnings Date"]
                    if dates and isinstance(dates, (list, tuple)):
                        for d in dates:
                            if isinstance(d, datetime):
                                d_date = d.date()
                            elif isinstance(d, date):
                                d_date = d
                            elif isinstance(d, str):
                                try:
                                    d_date = datetime.strptime(d[:10], "%Y-%m-%d").date()
                                except Exception:
                                    continue
                            else:
                                continue
                            if d_date >= today:
                                return d_date
                elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
                    series = cal.loc["Earnings Date"]
                    for val in series:
                        if pd.notna(val):
                            dt = pd.to_datetime(val).date()
                            if dt >= today:
                                return dt

            # 2. 备选尝试 t.get_earnings_dates
            try:
                earnings_df = t.get_earnings_dates(limit=8)
                if earnings_df is not None and not earnings_df.empty:
                    for idx in earnings_df.index:
                        dt = pd.to_datetime(idx).date()
                        if dt >= today:
                            return dt
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"通过 yfinance 获取 {ticker} 财报日历异常: {e}")

        return None

    def get_days_to_earnings(self, ticker: str, default_days: int = 30) -> int:
        """
        获取指定标的距离下一次财报发布的剩余自然日天数
        - 如果缓存命中且在 TTL 内，直接返回计算天数
        - 否则通过网络查询，更新缓存后返回
        - 失败或无数据时返回 default_days (默认 30 天)
        """
        if not ticker:
            return default_days

        ticker = ticker.upper().strip()
        now = time.time()
        today = date.today()

        # 1. 检查内存/磁盘缓存
        if ticker in self.cache:
            entry = self.cache[ticker]
            cached_time = entry.get("timestamp", 0)
            if now - cached_time < self.cache_ttl_seconds:
                next_date_str = entry.get("next_earnings_date")
                if next_date_str:
                    try:
                        next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                        delta = (next_date - today).days
                        return max(0, delta)
                    except Exception:
                        pass
                else:
                    # 记录了无财报/默认值的缓存
                    return entry.get("days_to_earnings", default_days)

        # 2. 缓存未命中或过期，执行查询
        next_date = self._extract_next_earnings_date_from_yf(ticker)
        if next_date is not None:
            days = max(0, (next_date - today).days)
            self.cache[ticker] = {
                "next_earnings_date": next_date.strftime("%Y-%m-%d"),
                "days_to_earnings": days,
                "timestamp": now,
            }
            self._save_cache()
            return days

        # 3. 未能查询到具体日期，缓存兜底值防止反复请求
        self.cache[ticker] = {
            "next_earnings_date": None,
            "days_to_earnings": default_days,
            "timestamp": now,
        }
        self._save_cache()
        return default_days

    def get_next_earnings_date(self, ticker: str) -> Optional[str]:
        """获取下一次财报的日期字符串 (格式: YYYY-MM-DD)"""
        ticker = ticker.upper().strip()
        # 确保缓存已填充
        self.get_days_to_earnings(ticker)
        entry = self.cache.get(ticker, {})
        return entry.get("next_earnings_date")

    def prefetch_universe(
        self,
        tickers: List[str],
        max_workers: int = 5,
        default_days: int = 30,
    ) -> Dict[str, int]:
        """
        多线程并发预加载标的池所有标的的财报日历缓存
        """
        results = {}
        now = time.time()
        tickers_to_fetch = []

        # 筛选出需要更新缓存的标的
        for t in tickers:
            t_upper = t.upper().strip()
            if t_upper in self.cache:
                entry = self.cache[t_upper]
                if now - entry.get("timestamp", 0) < self.cache_ttl_seconds:
                    results[t_upper] = self.get_days_to_earnings(t_upper, default_days=default_days)
                    continue
            tickers_to_fetch.append(t_upper)

        if not tickers_to_fetch:
            return results

        def _worker(sym: str) -> tuple[str, int]:
            return sym, self.get_days_to_earnings(sym, default_days=default_days)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            fetched = executor.map(_worker, tickers_to_fetch)
            for sym, days in fetched:
                results[sym] = days

        return results

    def clear_cache(self) -> None:
        """清空缓存"""
        self.cache.clear()
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception:
                pass
