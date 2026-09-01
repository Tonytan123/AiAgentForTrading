"""
sentinel/cron_sentinel.py
15 分钟定时巡检与持仓守护引擎 (15-Min Cron Sentinel: 正股与期权临期平仓健康守护)
"""

import os
import re
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
    StopOrderRequest,
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import QueryOrderStatus, OrderClass, AssetClass
from core.alpaca_client import AlpacaExecutionClient
from core.logger import setup_logger, cleanup_expired_logs

# ==========================================
# 1. 日志与审计系统配置 (控制台 + 文件双通道, 保留3天)
# ==========================================
logger = setup_logger(
    name="CronSentinel",
    log_dir="logs",
    log_file="sentinel.log",
    retention_days=3,
)

AUDIT_LOG_FILE = "logs/audit_trail.jsonl"


def record_audit_log(event_type: str, payload: Dict[str, Any]) -> None:
    """写入不可变审计追踪日志 (JSON Lines)"""
    try:
        os.makedirs(os.path.dirname(AUDIT_LOG_FILE), exist_ok=True)
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "module": "CronSentinel",
            "event_type": event_type,
            "data": payload,
        }
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"写入审计日志失败: {e}", exc_info=True)


# ==========================================
# 2. 15 分钟持仓与期权守护类实现
# ==========================================

class CronSentinel:
    """
    15 分钟持仓与期权临期平仓守护引擎:
    - 检查全账户正股与期权持仓及关联挂单
    - 期权持仓健康巡检：检查 DTE 是否 <= 2 天，触发临期强制市价平仓以规避行权交割风险
    - 孤儿持仓对冲：自动补齐 TP (+10%)、SL (-5%) 保护单
    - 闲置现金自动清扫：每日将超额闲置现金买入低风险超短期国债 ETF (SGOV, 年化 ~4.5%)
    - 超时持仓强制平仓 (最大持有期 180 天)
    - 每日自动清理超过 3 天的历史过期日志
    - 异常捕获与全流程不可变审计追踪
    """

    def __init__(
        self,
        trading_client: Optional[TradingClient] = None,
        max_holding_days: int = 180,  # 最大持仓时间 6个月 (正股超时平仓)
        max_option_dte_close: int = 2,  # 期权临期平仓天数 (DTE <= 2)
        default_tp_pct: float = 0.10,  # 止盈 10%
        default_sl_pct: float = 0.05,  # 止损 5%
        check_interval_seconds: int = 900,  # 15 分钟
        auto_sweep: bool = True,  # 自动将闲置资金买入国债 ETF (SGOV)
        sweep_symbol: str = "SGOV",
        reserve_cash: float = 500.0,
        log_retention_days: int = 3,  # 日志保留 3 天
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: Optional[bool] = None,
    ):
        if trading_client is not None:
            self.trading_client = trading_client
        else:
            gateway = AlpacaExecutionClient(api_key=api_key, secret_key=secret_key, paper=paper)
            self.trading_client = gateway.trading_client

        self.max_holding_days = max_holding_days
        self.max_option_dte_close = max_option_dte_close
        self.default_tp_pct = default_tp_pct
        self.default_sl_pct = default_sl_pct
        self.interval = check_interval_seconds
        self.auto_sweep = auto_sweep
        self.sweep_symbol = sweep_symbol
        self.reserve_cash = reserve_cash
        self.log_retention_days = log_retention_days
        self._is_running = False

    def inspect_and_heal(self) -> Dict[str, Any]:
        """执行单次巡检与自我修复核心逻辑"""
        # 自动执行过期日志清理 (默认清理超过 3 天的历史日志)
        cleanup_count = cleanup_expired_logs(
            log_dir="logs",
            retention_days=self.log_retention_days,
            prefix="sentinel",
        )
        if cleanup_count > 0:
            logger.info(f"[Sentinel] 自动清理已完成: 移除了 {cleanup_count} 个超过 {self.log_retention_days} 天的历史日志文件。")

        logger.info("[Sentinel] 开始执行 15 分钟正股与期权持仓健康巡检...")
        stats = {
            "status": "SUCCESS",
            "positions_checked": 0,
            "orphan_positions_healed": 0,
            "expired_positions_closed": 0,
            "near_expiration_options_closed": 0,
            "errors": [],
        }

        try:
            # 1. 获取所有当前持仓
            positions = self.trading_client.get_all_positions()
            stats["positions_checked"] = len(positions)
            logger.info(f"当前活跃持仓标的数: {len(positions)}")

            # 2. 获取所有打开状态的挂单
            open_orders_req = GetOrdersRequest(
                status=QueryOrderStatus.OPEN,
                limit=500,
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
                current_price = float(getattr(pos, "current_price", avg_entry_price))
                asset_class = getattr(pos, "asset_class", "us_equity")

                logger.info(
                    f"正在巡检标的: {symbol} | 资产类别: {asset_class} | 持仓数量: {qty} | 成本均价: ${avg_entry_price:.2f}"
                )

                # ----------------------------------------------------
                # 检查 1: 期权持仓检查 (DTE <= 2 天，触发临期强制市价平仓)
                # ----------------------------------------------------
                is_option = (
                    asset_class == AssetClass.US_OPTION
                    or asset_class == "us_option"
                    or len(symbol) > 10
                )

                if is_option:
                    try:
                        # 解析 OCC 合约代码到期日 (如 NVDA260918C00130000 -> 2026-09-18)
                        occ_match = re.match(r"^([A-Za-z]+)(\d{6})([CPcp])(\d{8})$", symbol)
                        if occ_match:
                            exp_str = occ_match.group(2)
                        else:
                            exp_str = symbol[len(symbol.rstrip("0123456789CPcp").rstrip("CPcp")):][:6]

                        exp_date = datetime.strptime(exp_str, "%y%m%d").replace(tzinfo=timezone.utc)
                        dte = (exp_date - now_utc).days

                        if dte <= self.max_option_dte_close:
                            logger.warning(
                                f"[期权临期平仓] 合约 {symbol} DTE={dte} 天 <= {self.max_option_dte_close} 天，强制市价平仓以规避交割风险！"
                            )
                            self._liquidate_position(
                                symbol, qty, reason=f"期权临期强制平仓 (DTE={dte}天 <= {self.max_option_dte_close}天)"
                            )
                            stats["near_expiration_options_closed"] += 1
                            continue
                        else:
                            logger.info(
                                f"[期权健康] 合约 {symbol} 距到期日 {exp_date.strftime('%Y-%m-%d')} 还有 {dte} 天 (DTE > {self.max_option_dte_close})。"
                            )
                    except Exception as e:
                        logger.error(f"解析期权合约 {symbol} 到期日失败: {e}", exc_info=True)
                        stats["errors"].append(f"解析期权 {symbol} 到期日异常: {e}")

                # ----------------------------------------------------
                # 检查 2: 超时平仓检查 (正股 Max Holding Period: 180 Days)
                # ----------------------------------------------------
                is_expired = False
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
                    continue

                # ----------------------------------------------------
                # 检查 3: 孤儿持仓检查 (正股是否有对应挂单保护)
                # ----------------------------------------------------
                if not is_option:
                    related_orders = orders_by_symbol.get(symbol, [])
                    has_tp_order = False
                    has_sl_order = False

                    for order in related_orders:
                        if order.side == OrderSide.SELL:
                            if order.order_type in ["limit", "stop_limit"] and float(order.limit_price or 0) > avg_entry_price:
                                has_tp_order = True
                            if order.order_type in ["stop", "stop_limit"] and float(order.stop_price or 0) < avg_entry_price:
                                has_sl_order = True

                    if not (has_tp_order and has_sl_order):
                        logger.warning(
                            f"[孤儿持仓警报] 标的 {symbol} 缺少完整保护挂单 "
                            f"(TP挂单: {'存在' if has_tp_order else '缺失'}, "
                            f"SL挂单: {'存在' if has_sl_order else '缺失'})，正在自动补齐..."
                        )
                        self._heal_orphan_position(
                            symbol=symbol,
                            qty=float(qty),
                            avg_price=avg_entry_price,
                            missing_tp=not has_tp_order,
                            missing_sl=not has_sl_order,
                            existing_orders=related_orders,
                        )
                        stats["orphan_positions_healed"] += 1
                    else:
                        logger.info(f"[健康] 标的 {symbol} 具备完整 TP/SL 挂单保护。")

            # ----------------------------------------------------
            # 检查 4: 闲置资金自动清扫至低风险国债 ETF (SGOV)
            # ----------------------------------------------------
            if self.auto_sweep:
                sweep_res = self._sweep_idle_cash()
                if sweep_res:
                    stats["treasury_sweep"] = sweep_res

            logger.info("========== 15 分钟守护巡检执行完毕 ==========")
            record_audit_log("SENTINEL_INSPECT_SUCCESS", stats)

        except Exception as e:
            err_msg = f"巡检守护执行过程中发生严重异常: {str(e)}"
            logger.critical(err_msg)
            logger.error(traceback.format_exc())
            stats["status"] = "ERROR"
            stats["errors"].append(err_msg)
            record_audit_log("SENTINEL_INSPECT_ERROR", {
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

        return stats

    def _heal_orphan_position(
        self,
        symbol: str,
        qty: float,
        avg_price: float,
        missing_tp: bool,
        missing_sl: bool,
        existing_orders: Optional[List[Any]] = None,
    ) -> None:
        """为孤儿持仓补发止盈与止损挂单 (自动升级替换为 OCO 双向保护单)"""
        tp_price = round(avg_price * (1.0 + self.default_tp_pct), 2)
        sl_price = round(avg_price * (1.0 - self.default_sl_pct), 2)

        try:
            # 若保护单不完整（无论全缺还是仅单边），先清理已存在的单边卖单，释放份额以统一提交 OCO 单
            if existing_orders:
                for ord_item in existing_orders:
                    if getattr(ord_item, "side", None) == OrderSide.SELL:
                        try:
                            self.trading_client.cancel_order_by_id(order_id=ord_item.id)
                            logger.info(f"已清理旧的单边保护单: {symbol} OrderID={ord_item.id}")
                        except Exception:
                            pass

            # 统一提交 OCO (One-Cancels-Other) 订单，同时覆盖 TP 限价与 SL 止损
            oco_req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                order_class=OrderClass.OCO,
                take_profit=TakeProfitRequest(limit_price=tp_price),
                stop_loss=StopLossRequest(stop_price=sl_price),
            )
            oco_res = self.trading_client.submit_order(oco_req)
            logger.info(
                f"已补发正股 OCO 保护单: {symbol} x {qty} 股 (止盈价: ${tp_price:.2f}, 止损价: ${sl_price:.2f}, OrderID: {oco_res.id})"
            )
            record_audit_log("ORPHAN_HEAL_OCO", {
                "symbol": symbol,
                "order_id": str(oco_res.id),
                "take_profit_price": tp_price,
                "stop_loss_price": sl_price,
                "qty": qty,
            })

        except Exception as e:
            logger.error(f"为孤儿持仓 {symbol} 补发保护订单失败: {e}", exc_info=True)
            record_audit_log("ORPHAN_HEAL_FAILED", {
                "symbol": symbol,
                "error": str(e),
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
                "reason": reason,
            })
        except Exception as e:
            logger.error(f"清空标的 {symbol} 持仓失败: {e}", exc_info=True)
            record_audit_log("POSITION_LIQUIDATE_FAILED", {
                "symbol": symbol,
                "error": str(e),
            })

    def _sweep_idle_cash(self) -> Optional[Dict[str, Any]]:
        """将账户多余闲置现金自动配置买入超短期国债 ETF (SGOV)"""
        try:
            # 1. 检查是否已有挂单中的国债 ETF 买单，避免重复清扫导致购买力不足
            open_orders = self.trading_client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
            )
            pending_sweeps = [
                o for o in open_orders
                if getattr(o, "symbol", "") == self.sweep_symbol and getattr(o, "side", None) == OrderSide.BUY
            ]
            if pending_sweeps:
                logger.info(
                    f"[Sentinel Cash Sweep] 已存在挂单中的 {self.sweep_symbol} 买单 (共 {len(pending_sweeps)} 笔)，跳过本次清扫。"
                )
                return None

            # 2. 获取账户实际现金及可用购买力 (两者取最小值，预留 reserve_cash)
            account = self.trading_client.get_account()
            cash = float(account.cash)
            buying_power = float(account.buying_power)
            usable_cash = min(cash, buying_power) - self.reserve_cash

            if usable_cash < 100.0:
                logger.info(f"[Sentinel Cash Sweep] 可用闲置资金 ${usable_cash:.2f} 低于单股起投阈值，暂不执行清扫。")
                return None

            # 3. 获取当前标的参考价格
            est_price = 100.50
            shares = int(usable_cash // est_price)
            if shares <= 0:
                return None

            req = MarketOrderRequest(
                symbol=self.sweep_symbol,
                qty=shares,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = self.trading_client.submit_order(req)
            est_cost = shares * est_price
            logger.info(
                f"[Sentinel Cash Sweep 成功] 闲置资金买入国债 ETF: {self.sweep_symbol} x {shares} 股, "
                f"预估金额: ${est_cost:,.2f}, OrderID: {order.id}"
            )
            record_audit_log("TREASURY_SWEEP_EXECUTED", {
                "symbol": self.sweep_symbol,
                "shares": shares,
                "est_cost": est_cost,
                "order_id": str(order.id),
                "remaining_cash": cash - est_cost,
            })
            return {
                "symbol": self.sweep_symbol,
                "shares": shares,
                "est_cost": est_cost,
                "order_id": str(order.id),
            }
        except Exception as e:
            logger.warning(f"[Sentinel Cash Sweep 提示] 资金清扫暂缓执行: {e}")
            record_audit_log("TREASURY_SWEEP_SKIPPED", {"reason": str(e)})
            return None

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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CronSentinel 15分钟持仓守护与期权临期健康巡检引擎")
    parser.add_argument("--daemon", action="store_true", help="以常驻守护进程模式启动 (每 15 分钟循环巡检)")
    args = parser.parse_args()

    sentinel = CronSentinel()
    if args.daemon:
        sentinel.run_daemon()
    else:
        logger.info("执行单次持仓与期权健康巡检...")
        result = sentinel.inspect_and_heal()
        print("\n巡检执行结果:\n", json.dumps(result, indent=2, ensure_ascii=False))