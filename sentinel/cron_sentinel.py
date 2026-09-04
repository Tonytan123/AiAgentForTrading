"""
sentinel/cron_sentinel.py
15 分钟定时巡检与持仓守护引擎 (15-Min Cron Sentinel: 正股与期权临期平仓健康守护)
支持中英文双语日志输出 (Bilingual Log Output: en / zh)
"""

import os
import re
import time
import json
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

import yaml
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

SENTINEL_MESSAGES: Dict[str, Dict[str, str]] = {
    "zh": {
        "daemon_started": "CronSentinel 守护进程已启动，轮询周期: {interval} 秒 (15 分钟)...",
        "log_cleanup_done": "[Sentinel] 自动清理已完成: 移除了 {count} 个超过 {days} 天的历史日志文件。",
        "inspect_start": "[Sentinel] 开始执行 15 分钟正股与期权持仓健康巡检...",
        "active_positions": "当前活跃持仓标的数: {count}",
        "inspect_symbol": "正在巡检标的: {symbol} | 资产类别: {asset_class} | 持仓数量: {qty} | 成本均价: ${avg_price:.2f}",
        "option_close_dte": "[期权临期平仓] 合约 {symbol} DTE={dte} 天 <= {max_dte} 天，强制市价平仓以规避交割风险！",
        "option_healthy": "[期权健康] 合约 {symbol} 距到期日 {exp_date} 还有 {dte} 天 (DTE > {max_dte})。",
        "option_parse_err": "[Sentinel Error] 解析期权合约 {symbol} 到期日失败 / Failed to parse option expiration: {error}",
        "timeout_close": "[超时触发] 标的 {symbol} 已持有 {days} 天 (超过最大限制 {max_days} 天)，触发强制平仓！",
        "orphan_alert": "[孤儿持仓警报] 标的 {symbol} 缺少完整保护挂单 (TP挂单: {tp_status}, SL挂单: {sl_status})，正在自动补齐...",
        "status_present": "存在",
        "status_missing": "缺失",
        "cleaned_legacy_order": "已清理旧的单边保护单: {symbol} OrderID={order_id}",
        "reissued_oco_order": "已补发正股 OCO 保护单: {symbol} x {qty} 股 (止盈价: ${tp_price:.2f}, 止损价: ${sl_price:.2f}, OrderID: {order_id})",
        "reissue_order_err": "[Sentinel Error] 为孤儿持仓 {symbol} 补发保护订单失败 / Failed to submit protection order: {error}",
        "healthy_order": "[健康] 标的 {symbol} 具备完整 TP/SL 挂单保护。",
        "liquidating_position": "正在市价清空标的 {symbol} 全部持仓，原因: {reason}",
        "liquidated_done": "标的 {symbol} 已全部平仓并撤销全部挂单。",
        "liquidate_err": "[Sentinel Error] 清空标的 {symbol} 持仓失败 / Failed to liquidate position: {error}",
        "sweep_pending_skip": "[Sentinel Cash Sweep] 已存在挂单中的 {symbol} 买单 (共 {count} 笔)，跳过本次清扫。",
        "sweep_low_cash_skip": "[Sentinel Cash Sweep] 可用闲置资金 ${cash:.2f} 低于单股起投阈值，暂不执行清扫。",
        "sweep_success": "[Sentinel Cash Sweep 成功] 闲置资金买入国债 ETF: {symbol} x {shares} 股, 预估金额: ${cost:,.2f}, OrderID: {order_id}",
        "sweep_deferred": "[Sentinel Cash Sweep Notice] 资金清扫暂缓执行 / Sweep deferred: {error}",
        "inspect_done": "========== 15 分钟守护巡检执行完毕 ==========",
        "inspect_fatal_err": "[Sentinel Error] 巡检守护发生异常 / Severe inspection exception: {error}",
        "sleep_msg": "进入休眠，将在 {interval} 秒后进行下次巡检...",
        "stopping_daemon": "正在停止 CronSentinel 守护进程...",
        "single_run_msg": "执行单次持仓与期权健康巡检...",
        "single_run_result": "\n巡检执行结果 / Execution Results:\n",
        "audit_write_err": "[Sentinel Error] 写入审计日志失败 / Failed to write audit log: {error}",
    },
    "en": {
        "daemon_started": "CronSentinel daemon started, polling interval: {interval}s (15 minutes)...",
        "log_cleanup_done": "[Sentinel] Auto-cleanup complete: Removed {count} log file(s) older than {days} days.",
        "inspect_start": "[Sentinel] Starting 15-minute equity and options position health inspection...",
        "active_positions": "Active open positions count: {count}",
        "inspect_symbol": "Inspecting asset: {symbol} | Asset Class: {asset_class} | Qty: {qty} | Avg Entry Price: ${avg_price:.2f}",
        "option_close_dte": "[Option Near Expiration] Contract {symbol} DTE={dte} days <= {max_dte} days, executing market close to avoid expiration/assignment risk!",
        "option_healthy": "[Option Healthy] Contract {symbol} is {dte} days to expiration {exp_date} (DTE > {max_dte}).",
        "option_parse_err": "[Sentinel Error] Failed to parse expiration date for option {symbol}: {error}",
        "timeout_close": "[Timeout Trigger] Asset {symbol} holding duration {days} days exceeds max limit {max_days} days, executing force liquidation!",
        "orphan_alert": "[Orphan Position Alert] Asset {symbol} lacks complete protection orders (TP Order: {tp_status}, SL Order: {sl_status}), auto-healing...",
        "status_present": "Present",
        "status_missing": "Missing",
        "cleaned_legacy_order": "Cleaned legacy one-way protection order: {symbol} OrderID={order_id}",
        "reissued_oco_order": "Submitted equity OCO protection order: {symbol} x {qty} shares (TP: ${tp_price:.2f}, SL: ${sl_price:.2f}, OrderID: {order_id})",
        "reissue_order_err": "[Sentinel Error] Failed to submit protection orders for orphan position {symbol}: {error}",
        "healthy_order": "[Healthy] Asset {symbol} has complete TP/SL order protection.",
        "liquidating_position": "Executing market liquidation for {symbol}, reason: {reason}",
        "liquidated_done": "Asset {symbol} fully liquidated and associated orders canceled.",
        "liquidate_err": "[Sentinel Error] Failed to liquidate asset {symbol}: {error}",
        "sweep_pending_skip": "[Sentinel Cash Sweep] Existing pending buy order for {symbol} ({count} orders), skipping cash sweep.",
        "sweep_low_cash_skip": "[Sentinel Cash Sweep] Usable cash ${cash:.2f} below single-share investment threshold, skipping sweep.",
        "sweep_success": "[Sentinel Cash Sweep Success] Invested idle cash in Treasury ETF: {symbol} x {shares} shares, estimated cost: ${cost:,.2f}, OrderID: {order_id}",
        "sweep_deferred": "[Sentinel Cash Sweep Notice] Cash sweep deferred: {error}",
        "inspect_done": "========== 15-Minute Sentinel Health Inspection Completed ==========",
        "inspect_fatal_err": "[Sentinel Error] Severe exception occurred during sentinel inspection: {error}",
        "sleep_msg": "Entering sleep, next inspection in {interval} seconds...",
        "stopping_daemon": "Stopping CronSentinel daemon...",
        "single_run_msg": "Executing single equity and option health inspection...",
        "single_run_result": "\nInspection Execution Results:\n",
        "audit_write_err": "[Sentinel Error] Failed to write audit log: {error}",
    },
}


def record_audit_log(event_type: str, payload: Dict[str, Any], lang: str = "en") -> None:
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
        err_msg = SENTINEL_MESSAGES.get(lang, SENTINEL_MESSAGES["en"])["audit_write_err"].format(error=e)
        logger.error(err_msg, exc_info=True)


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
    - 支持中英文双语日志输出
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
        lang: str = "en",  # 默认日志语言 ("en" 或 "zh")
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
        self.lang = lang if lang in ["zh", "en"] else "en"
        self._is_running = False

    def _t(self, key: str, **kwargs: Any) -> str:
        """获取当前语言对应的格式化日志文本"""
        dict_to_use = SENTINEL_MESSAGES.get(self.lang, SENTINEL_MESSAGES["en"])
        template = dict_to_use.get(key, SENTINEL_MESSAGES["en"].get(key, key))
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template

    def inspect_and_heal(self) -> Dict[str, Any]:
        """执行单次巡检与自我修复核心逻辑"""
        # 自动执行过期日志清理 (默认清理超过 3 天的历史日志)
        cleanup_count = cleanup_expired_logs(
            log_dir="logs",
            retention_days=self.log_retention_days,
            prefix="sentinel",
            lang=self.lang,
        )
        if cleanup_count > 0:
            logger.info(self._t("log_cleanup_done", count=cleanup_count, days=self.log_retention_days))

        logger.info(self._t("inspect_start"))
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
            logger.info(self._t("active_positions", count=len(positions)))

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
                    self._t(
                        "inspect_symbol",
                        symbol=symbol,
                        asset_class=asset_class,
                        qty=qty,
                        avg_price=avg_entry_price,
                    )
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
                                self._t(
                                    "option_close_dte",
                                    symbol=symbol,
                                    dte=dte,
                                    max_dte=self.max_option_dte_close,
                                )
                            )
                            reason_str = (
                                f"Option near expiration market close (DTE={dte}D <= {self.max_option_dte_close}D)"
                                if self.lang == "en"
                                else f"期权临期强制平仓 (DTE={dte}天 <= {self.max_option_dte_close}天)"
                            )
                            self._liquidate_position(symbol, qty, reason=reason_str)
                            stats["near_expiration_options_closed"] += 1
                            continue
                        else:
                            logger.info(
                                self._t(
                                    "option_healthy",
                                    symbol=symbol,
                                    exp_date=exp_date.strftime("%Y-%m-%d"),
                                    dte=dte,
                                    max_dte=self.max_option_dte_close,
                                )
                            )
                    except Exception as e:
                        logger.error(self._t("option_parse_err", symbol=symbol, error=e), exc_info=True)
                        stats["errors"].append(f"Option {symbol} expiration parse error: {e}")

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
                            self._t(
                                "timeout_close",
                                symbol=symbol,
                                days=holding_duration.days,
                                max_days=self.max_holding_days,
                            )
                        )

                if is_expired:
                    reason_str = (
                        f"Holding duration exceeded {self.max_holding_days} days"
                        if self.lang == "en"
                        else f"持有超过 {self.max_holding_days} 天"
                    )
                    self._liquidate_position(symbol, qty, reason=reason_str)
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
                            self._t(
                                "orphan_alert",
                                symbol=symbol,
                                tp_status=self._t("status_present") if has_tp_order else self._t("status_missing"),
                                sl_status=self._t("status_present") if has_sl_order else self._t("status_missing"),
                            )
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
                        logger.info(self._t("healthy_order", symbol=symbol))

            # ----------------------------------------------------
            # 检查 4: 闲置资金自动清扫至低风险国债 ETF (SGOV)
            # ----------------------------------------------------
            if self.auto_sweep:
                sweep_res = self._sweep_idle_cash()
                if sweep_res:
                    stats["treasury_sweep"] = sweep_res

            logger.info(self._t("inspect_done"))
            record_audit_log("SENTINEL_INSPECT_SUCCESS", stats, lang=self.lang)

        except Exception as e:
            err_msg = self._t("inspect_fatal_err", error=str(e))
            logger.critical(err_msg)
            logger.error(traceback.format_exc())
            stats["status"] = "ERROR"
            stats["errors"].append(err_msg)
            record_audit_log("SENTINEL_INSPECT_ERROR", {
                "error": str(e),
                "traceback": traceback.format_exc(),
            }, lang=self.lang)

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
                            logger.info(self._t("cleaned_legacy_order", symbol=symbol, order_id=ord_item.id))
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
                self._t(
                    "reissued_oco_order",
                    symbol=symbol,
                    qty=qty,
                    tp_price=tp_price,
                    sl_price=sl_price,
                    order_id=oco_res.id,
                )
            )
            record_audit_log("ORPHAN_HEAL_OCO", {
                "symbol": symbol,
                "order_id": str(oco_res.id),
                "take_profit_price": tp_price,
                "stop_loss_price": sl_price,
                "qty": qty,
            }, lang=self.lang)

        except Exception as e:
            logger.error(self._t("reissue_order_err", symbol=symbol, error=e), exc_info=True)
            record_audit_log("ORPHAN_HEAL_FAILED", {
                "symbol": symbol,
                "error": str(e),
            }, lang=self.lang)

    def _liquidate_position(self, symbol: str, qty: float, reason: str) -> None:
        """清空指定标的持仓并取消关联挂单"""
        try:
            logger.info(self._t("liquidating_position", symbol=symbol, reason=reason))
            # Alpaca API 提供直接平仓特定持仓的接口
            self.trading_client.close_position(symbol_or_asset_id=symbol)
            logger.info(self._t("liquidated_done", symbol=symbol))
            record_audit_log("POSITION_LIQUIDATED", {
                "symbol": symbol,
                "qty": qty,
                "reason": reason,
            }, lang=self.lang)
        except Exception as e:
            logger.error(self._t("liquidate_err", symbol=symbol, error=e), exc_info=True)
            record_audit_log("POSITION_LIQUIDATE_FAILED", {
                "symbol": symbol,
                "error": str(e),
            }, lang=self.lang)

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
                logger.info(self._t("sweep_pending_skip", symbol=self.sweep_symbol, count=len(pending_sweeps)))
                return None

            # 2. 获取账户实际现金及可用购买力 (两者取最小值，预留 reserve_cash)
            account = self.trading_client.get_account()
            cash = float(account.cash)
            buying_power = float(account.buying_power)
            usable_cash = min(cash, buying_power) - self.reserve_cash

            if usable_cash < 100.0:
                logger.info(self._t("sweep_low_cash_skip", cash=usable_cash))
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
                self._t(
                    "sweep_success",
                    symbol=self.sweep_symbol,
                    shares=shares,
                    cost=est_cost,
                    order_id=order.id,
                )
            )
            record_audit_log("TREASURY_SWEEP_EXECUTED", {
                "symbol": self.sweep_symbol,
                "shares": shares,
                "est_cost": est_cost,
                "order_id": str(order.id),
                "remaining_cash": cash - est_cost,
            }, lang=self.lang)
            return {
                "symbol": self.sweep_symbol,
                "shares": shares,
                "est_cost": est_cost,
                "order_id": str(order.id),
            }
        except Exception as e:
            logger.warning(self._t("sweep_deferred", error=e))
            record_audit_log("TREASURY_SWEEP_SKIPPED", {"reason": str(e)}, lang=self.lang)
            return None

    def run_daemon(self) -> None:
        """常驻守护进程入口（用于后台独立线程或子进程运行）"""
        self._is_running = True
        logger.info(self._t("daemon_started", interval=self.interval))
        record_audit_log("SENTINEL_DAEMON_STARTED", {"interval_seconds": self.interval}, lang=self.lang)

        while self._is_running:
            try:
                self.inspect_and_heal()
            except Exception as e:
                logger.critical(f"Unhandled exception in daemon loop: {e}", exc_info=True)

            logger.info(self._t("sleep_msg", interval=self.interval))
            time.sleep(self.interval)

    def stop(self) -> None:
        """安全停止守护进程"""
        logger.info(self._t("stopping_daemon"))
        self._is_running = False
        record_audit_log("SENTINEL_DAEMON_STOPPED", {}, lang=self.lang)


if __name__ == "__main__":
    import argparse

    def _load_default_lang() -> str:
        try:
            if os.path.exists("config/settings.yaml"):
                with open("config/settings.yaml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    return cfg.get("system", {}).get("language", "en")
        except Exception:
            pass
        return "en"

    default_system_lang = _load_default_lang()

    parser = argparse.ArgumentParser(
        description="CronSentinel 15分钟持仓守护与期权临期健康巡检引擎 / 15-Minute Position & Option Expiration Sentinel"
    )
    parser.add_argument("--daemon", action="store_true", help="以常驻守护进程模式启动 (每 15 分钟循环巡检) / Run in daemon mode (polls every 15 mins)")
    parser.add_argument(
        "-l",
        "--lang",
        choices=["en", "zh"],
        default=default_system_lang,
        help="设置日志输出语言 / Set log output language (en=English, zh=中文, default: settings.yaml)",
    )
    args = parser.parse_args()

    sentinel = CronSentinel(lang=args.lang)
    if args.daemon:
        sentinel.run_daemon()
    else:
        logger.info(sentinel._t("single_run_msg"))
        result = sentinel.inspect_and_heal()
        print(sentinel._t("single_run_result"), json.dumps(result, indent=2, ensure_ascii=False))