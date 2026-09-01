"""Unit tests for core.logger module."""

import os
import time
import tempfile
import logging
from core.logger import setup_logger, cleanup_expired_logs


def test_setup_logger_dual_handlers():
    """测试 setup_logger 同时创建控制台与文件处理器"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_logger_name = f"TestLogger_{int(time.time()*1000)}"
        logger = setup_logger(
            name=test_logger_name,
            log_dir=tmpdir,
            log_file="test_sentinel.log",
            retention_days=3,
        )

        assert len(logger.handlers) == 2
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "TimedRotatingFileHandler" in handler_types

        # 写入一条测试日志
        logger.info("测试巡检日志双向输出消息 (UTF-8 兼容性测试)")

        # 验证文件被正确写入且内容包含该日志
        log_path = os.path.join(tmpdir, "test_sentinel.log")
        assert os.path.exists(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "测试巡检日志双向输出消息" in content

        # 在 Windows 上清理前关闭文件 handler
        for h in list(logger.handlers):
            h.close()
            logger.removeHandler(h)


def test_cleanup_expired_logs():
    """测试 cleanup_expired_logs 清理 3 天前过期日志并保留有效日志"""
    with tempfile.TemporaryDirectory() as tmpdir:
        now = time.time()
        one_day_ago = now - (1 * 86400)
        two_days_ago = now - (2 * 86400)
        four_days_ago = now - (4 * 86400)
        seven_days_ago = now - (7 * 86400)

        # 1. 创建基础当前活跃日志 (应始终保留)
        base_log = os.path.join(tmpdir, "sentinel.log")
        with open(base_log, "w", encoding="utf-8") as f:
            f.write("active log\n")
        os.utime(base_log, (four_days_ago, four_days_ago))

        # 2. 创建 1 天与 2 天前的历史轮转日志 (应保留)
        recent_log1 = os.path.join(tmpdir, "sentinel.log.2026-08-31")
        with open(recent_log1, "w", encoding="utf-8") as f:
            f.write("recent log 1\n")
        os.utime(recent_log1, (one_day_ago, one_day_ago))

        recent_log2 = os.path.join(tmpdir, "sentinel.log.2026-08-30")
        with open(recent_log2, "w", encoding="utf-8") as f:
            f.write("recent log 2\n")
        os.utime(recent_log2, (two_days_ago, two_days_ago))

        # 3. 创建 4 天与 7 天前的过期历史日志 (应被清理删除)
        old_log1 = os.path.join(tmpdir, "sentinel.log.2026-08-28")
        with open(old_log1, "w", encoding="utf-8") as f:
            f.write("old log 1\n")
        os.utime(old_log1, (four_days_ago, four_days_ago))

        old_log2 = os.path.join(tmpdir, "sentinel.log.2026-08-25")
        with open(old_log2, "w", encoding="utf-8") as f:
            f.write("old log 2\n")
        os.utime(old_log2, (seven_days_ago, seven_days_ago))

        # 执行清理 (保留 3 天)
        deleted = cleanup_expired_logs(log_dir=tmpdir, retention_days=3, prefix="sentinel")

        assert deleted == 2
        # 验证活跃基础日志与最近 2 天日志完好存在
        assert os.path.exists(base_log)
        assert os.path.exists(recent_log1)
        assert os.path.exists(recent_log2)
        # 验证超过 3 天的旧日志已被删除
        assert not os.path.exists(old_log1)
        assert not os.path.exists(old_log2)
