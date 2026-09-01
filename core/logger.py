"""
core/logger.py
统一日志与轮转生命周期管理基础设施
支持 Console 控制台 + File 文件的双通道输出，以及基于天数的过期日志自动清理机制。
"""

import os
import glob
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = "CronSentinel",
    log_dir: str = "logs",
    log_file: str = "sentinel.log",
    retention_days: int = 3,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    配置并获取双通道 Logger:
    1. 控制台 StreamHandler 实时输出
    2. 按日轮转 TimedRotatingFileHandler 文件持久化 (UTF-8 编码, 保留 retention_days 天)
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 Handler
    if logger.handlers:
        return logger

    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 1. 控制台输出 Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. 每日午夜轮转的文件持久化 Handler (保留 retention_days 份历史文件)
    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        delay=False,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def cleanup_expired_logs(
    log_dir: str = "logs",
    retention_days: int = 3,
    prefix: str = "sentinel",
) -> int:
    """
    扫描并清理 logs 目录下已超过 retention_days (默认 3 天) 的历史日志文件
    返回已删除的文件数量
    """
    if not os.path.exists(log_dir):
        return 0

    deleted_count = 0
    now = time.time()
    cutoff_time = now - (retention_days * 86400)

    # 匹配各类日志文件如: sentinel.log.2026-08-28, sentinel_20260828.log 等
    pattern = os.path.join(log_dir, f"{prefix}*")
    matching_files = glob.glob(pattern)

    for file_path in matching_files:
        # 排除当前正在写入的基础日志文件 (如 sentinel.log)
        base_name = os.path.basename(file_path)
        if base_name == f"{prefix}.log":
            continue

        try:
            mtime = os.path.getmtime(file_path)
            if mtime < cutoff_time:
                os.remove(file_path)
                deleted_count += 1
                logging.getLogger("CronSentinel").info(
                    f"[Log Cleanup] 已清理超过 {retention_days} 天的历史过期日志: {base_name}"
                )
        except Exception as e:
            logging.getLogger("CronSentinel").warning(
                f"[Log Cleanup] 清理日志文件 {base_name} 失败: {e}"
            )

    return deleted_count
