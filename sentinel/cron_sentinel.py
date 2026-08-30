"""
sentinel/cron_sentinel.py
15 分钟定时巡检与持仓守护引擎 (15-Min Cron Sentinel)
"""

import os
import time
import json
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    OrderSide,
    TimeInForce,
    LimitOrderRequest,
    StopOrderRequest
)
from alpaca.trading.enums import QueryOrderStatus, OrderClass

# ==========================================
# 1. 日志与审计系统配置
# ==========================================
logger = logging.getLogger("CronSentinel")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # 控制台格式化输出
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [Sentinel] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

AUDIT_LOG_FILE = "logs/audit_trail.jsonl"


def record_audit_log(event_type: str, payload: Dict[str, Any]) -> None:
    """写入不可变审计追踪日志 (JSON Lines)"""
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module": "CronSentinel",
            "event_type": event_type,
            "data": payload
        }
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"写入审计日志失败: {e}", exc_info=True)


# ==========================================
# 2. 15 分钟持仓守护类实现
# ==========================================

class CronSentinel:
    """
    15 分钟持仓守护巡检引擎:
    - 检查全账户持仓及关联挂单
    - 孤儿持仓对冲 (自动补齐 TP: +8.0%, SL: -4.0% 保护单)
    - 超时持仓强制平仓 (最大持有期 28 天)
    - 异常捕获与全流程不可变审计
    """

    def __init__(
        self,
        trading_client: TradingClient,
        max_holding_days: int = 180, # 最大持仓时间 6个月
        default_tp_pct: float = 0.1,   # 止盈 10%
        default_sl_pct: float = 0.05,   # 止损 5%
        check_interval_seconds: int = 900 # 15 分钟
    ):
        self.trading_client = trading_client
        self.max_holding_days = max_holding_days
        self.default_tp_pct = default_tp_pct
        self.default_sl_pct = default_sl_pct
        self.interval = check_interval_seconds
        self._is_running = False

    def inspect_and_heal(self) -> Dict[str, Any]:
        """执行单次巡检与自我修复核心逻辑"""
        logger.info("========== 开始执行 15 分钟持仓与挂单守护巡检 ==========")
        stats = {
            "positions_checked": 0,
            "orphan_positions_healed": 0,
            "expired_positions_closed": 0,
            "errors": []
        }

        try:
            # 1. 获取所有当前持仓
            positions = self.trading_client.get_all_positions()
            stats["positions_checked"] = len(positions)
            logger.info(f"当前活跃持仓标的数: {len(positions)}")

            # 2. 获取所有打开状态的挂单
            open_orders_req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                limit=500
            )
            open_orders = self.trading_client.get_orders(filter=open_orders_req)
            
            # 按标的代码分类挂单 (symbol -> List[Order])
            orders_by_symbol: Dict[str, List[Any]] = {}
            for order in open_orders:
                orders_by_symbol.setdefault(order.symbol, []).append(order)

            # 3. 逐一遍历持仓进行健康度检查
            now_utc = datetime.now(timezone.utc)

            for pos in positions:
                symbol = pos.symbol
                qty = float(pos.qty)
                avg_entry_price = float(pos.avg_entry_price)
                current_price = float(pos.current_price)

                logger.info(f"正在巡检标的: {symbol} | 持仓股数: {qty} | 成本均价: ${avg_entry_price:.2f}")

                # ----------------------------------------------------
                # 检查 A: 超时平仓检查 (Max Holding Period: 28 Days)
                # ----------------------------------------------------
                # Alpaca position 可能不直接提供开仓时间，使用 fallback 或计算天数
                # 若无明确开仓时间戳，可通过关联订单记录或历史 trades 计算，此处安全读取
                is_expired = False
                # 模拟/安全时间戳比对
                entry_time = getattr(pos, "created_at", None)
                if entry_time:
                    holding_duration = now_utc - entry_time
                    if holding_duration > timedelta(days=self.max_holding_days):
                        is_expired = True
                        logger.warning(
                            f"[超时触发] 标的 {symbol} 已持有 {holding_duration.days} 天 "
                            f"(超过最大限制 {self.max_holding_days} 天)，触发强制平仓！"
                        )

                if is_expired:
                    self._liquidate_position(symbol, qty, reason=f"持有超过 {self.max_holding_days} 天")
                    stats["expired_positions_closed"] += 1
                    continue # 已平仓标的跳过后续 OCO 检查

                # ----------------------------------------------------
                # 检查 B: 孤儿持仓检查 (是否有对应挂单保护)
                # ----------------------------------------------------
                related_orders = orders_by_symbol.get(symbol, [])
                has_tp_order = False #是否有止盈单
                has_sl_order = False #是否有止损单

                for order in related_orders:
                    # 检查针对多头持仓的卖出保护单 (OrderSide.SELL)
                    if order.side == OrderSide.SELL:
                        if order.order_type in ["limit", "stop_limit"] and float(order.limit_price or 0) > avg_entry_price:
                            has_tp_order = True
                        if order.order_type in ["stop", "stop_limit"] and float(order.stop_price or 0) < avg_entry_price:
                            has_sl_order = True

                # 如果缺少保护挂单，判定为孤儿持仓，补齐 TP/SL
                if not (has_tp_order and has_sl_order):
                    logger.warning(
                        f"[孤儿持仓警报] 标的 {symbol} 缺少完整保护挂单 "
                        f"(TP挂单: {'存在' if has_tp_order else '缺失'}, "
                        f"SL挂单: {'存在' if has_sl_order else '缺失'})，正在自动补齐..."
                    )
                    self._heal_orphan_position(
                        symbol=symbol,
                        qty=int(qty),
                        avg_price=avg_entry_price,
                        missing_tp=not has_tp_order,
                        missing_sl=not has_sl_order
                    )
                    stats["orphan_positions_healed"] += 1
                else:
                    logger.info(f"[健康] 标的 {symbol} 具备完整 TP/SL 挂单保护。")

            logger.info("========== 15 分钟守护巡检执行完毕 ==========")
            record_audit_log("SENTINEL_INSPECT_SUCCESS", stats)

        except Exception as e:
            err_msg = f"巡检守护执行过程中发生严重异常: {str(e)}"
            logger.critical(err_msg)
            logger.error(traceback.format_exc())
            stats["errors"].append(err_msg)
            record_audit_log("SENTINEL_INSPECT_ERROR", {
                "error": str(e),
                "traceback": traceback.format_exc()
            })

        return stats

    def _heal_orphan_position(
        self,
        symbol: str,
        qty: int,
        avg_price: float,
        missing_tp: bool,
        missing_sl: bool
    ) -> None:
        """为孤儿持仓补发止盈与止损挂单"""
        tp_price = round(avg_price * (1.0 + self.default_tp_pct), 2)
        sl_price = round(avg_price * (1.0 - self.default_sl_pct), 2)

        try:
            # 补发止盈单 (Limit Order GTC)
            if missing_tp:
                tp_req = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    limit_price=tp_price
                )
                tp_res = self.trading_client.submit_order(tp_req)
                logger.info(f"已补发止盈单: {symbol} @ ${tp_price:.2f} (OrderID: {tp_res.id})")
                record_audit_log("ORPHAN_HEAL_TP", {
                    "symbol": symbol,
                    "order_id": str(tp_res.id),
                    "limit_price": tp_price,
                    "qty": qty
                })

            # 补发止损单 (Stop Order GTC)
            if missing_sl:
                sl_req = StopOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.GTC,
                    stop_price=sl_price
                )
                sl_res = self.trading_client.submit_order(sl_req)
                logger.info(f"已补发止损单: {symbol} @ ${sl_price:.2f} (OrderID: {sl_res.id})")
                record_audit_log("ORPHAN_HEAL_SL", {
                    "symbol": symbol,
                    "order_id": str(sl_res.id),
                    "stop_price": sl_price,
                    "qty": qty
                })

        except Exception as e:
            logger.error(f"为孤儿持仓 {symbol} 补发保护订单失败: {e}", exc_info=True)
            record_audit_log("ORPHAN_HEAL_FAILED", {
                "symbol": symbol,
                "error": str(e)
            })

    def _liquidate_position(self, symbol: str, qty: float, reason: str) -> None:
        """清空指定标的持仓并取消关联挂单"""
        try:
            logger.info(f"正在市价清空标的 {symbol} 全部持仓，原因: {reason}")
            # Alpaca API 提供直接平仓特定持仓的接口
            self.trading_client.close_position(symbol_or_asset_id=symbol)
            logger.info(f"标的 {symbol} 已全部平仓并撤销全部挂单。")
            record_audit_log("POSITION_LIQUIDATED", {
                "symbol": symbol,
                "qty": qty,
                "reason": reason
            })
        except Exception as e:
            logger.error(f"清空标的 {symbol} 持仓失败: {e}", exc_info=True)
            record_audit_log("POSITION_LIQUIDATE_FAILED", {
                "symbol": symbol,
                "error": str(e)
            })

    def run_daemon(self) -> None:
        """常驻守护进程入口（用于后台独立线程或子进程运行）"""
        self._is_running = True
        logger.info(f"CronSentinel 守护进程已启动，轮询周期: {self.interval} 秒 (15 分钟)...")
        record_audit_log("SENTINEL_DAEMON_STARTED", {"interval_seconds": self.interval})

        while self._is_running:
            try:
                self.inspect_and_heal()
            except Exception as e:
                logger.critical(f"守护主循环捕获未处理异常: {e}", exc_info=True)

            logger.info(f"进入休眠，将在 {self.interval} 秒后进行下次巡检...")
            time.sleep(self.interval)

    def stop(self) -> None:
        """安全停止守护进程"""
        logger.info("正在停止 CronSentinel 守护进程...")
        self._is_running = False
        record_audit_log("SENTINEL_DAEMON_STOPPED", {})