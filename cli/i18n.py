"""
cli/i18n.py
多语言国际化模块 (Internationalization / Localization for Trading Terminal)
支持中英文 (zh / en) 动态切换、全局翻译与局部传参
"""

from typing import Dict, Any, Optional

LANG_ZH = "zh"
LANG_EN = "en"

_CURRENT_LANG = LANG_EN

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    LANG_ZH: {
        # 通用与系统
        "app_title": "AiAgentForTrading 交互式量化交易系统终端",
        "connecting_alpaca": "[*] 正在从 Alpaca 同步真实账户资产状态与挂单...",
        "scanning_market": "[*] 正在对全市场 {count} 支标的启动五大智能体真实辩论扫盘 (Regime: {regime})...",
        "macro_status_title": "账户与宏观状态总览",
        "col_equity": "账户总净值 (Equity)",
        "col_buying_power": "可用购买力 (Buying Power)",
        "col_cash": "现金余额 (Cash)",
        "col_sgov": "国债理财 (SGOV)",
        "col_day_pnl": "当日盈亏比例",
        "col_vix": "VIX 指数",
        "col_hy_spread": "高收益利差",
        "col_regime": "宏观模式",
        "fetching_universe": "[*] 正在从标的池 (共 {count} 支标的) 获取最新市场快照...",
        "universe_table_title": "标普 500 核心标的行情池",
        "col_u_idx": "序号",
        "col_u_ticker": "代码 (Ticker)",
        "col_u_price": "最新市价",
        "col_u_chg": "当日涨跌幅",
        "col_u_rsi": "RSI (14D)",
        "col_u_vol": "成交量 (Volume)",
        "main_prompt": "请输入要分析交易的 标的代码 或 序号 (输入 'S'=一键扫盘, 'P'=查看/卖出持仓, 'O'=查看未成交挂单, 'L'/'EN'/'ZH'=切换中英文, 'exit'/'q'=退出)",
        "exit_success": "已退出交易系统。祝您投资顺利！",
        "language_switched": "界面语言已切换 / Language switched successfully!",
        "lang_switched_zh": "界面语言已切换为: 简体中文 (Chinese)",
        "lang_switched_en": "Language switched to: English (英文)",
        "scanner_quick_prompt": "请输入推荐标的 序号 或 代码 直接进入决策 (直接按 Enter 返回主菜单)",
        "press_enter_back": "按 Enter 键返回主菜单",
        "press_enter_refresh": "按 Enter 键刷新列表",
        "press_enter_continue": "按 Enter 键继续",
        "invalid_ticker": "错误: 标的 {ticker} 不在允许的白名单标的池内！请重新选择。",
        "trade_mode_prompt": "请选择交易倾向 [AUTO=智能混合决策, EQUITY=仅正股, OPTION=仅期权]",
        "selected_ticker_info": ">>> 已选中标的: {ticker} (当前市价: ${price:.2f}, 倾向: {mode})",
        "calling_agents": "[*] 正在唤起 5 大策略研究智能体并行分析辩论...",

        # 投资备忘录 Panel 与 Critic
        "memo_title": "智能投资决策备忘录 ({asset_type})",
        "memo_proposal_id": "提案ID",
        "memo_category": "资产类型",
        "memo_contract_symbol": "期权合约",
        "memo_action": "交易动作",
        "memo_suggested_contracts": "建议张数",
        "memo_total_premium": "总权利金",
        "memo_take_profit": "目标止盈",
        "memo_stop_loss": "严格止损",
        "memo_target_symbol": "标的代码",
        "memo_current_price": "最新市价",
        "memo_suggested_shares": "建议股数",
        "memo_agent_debate_section": "【5 大策略智能体辩论评估】",
        "memo_consensus_score": "综合加权共识分: {score:.2f} / 1.00 (门槛: 0.70)",
        "memo_critic_section": "【Critic 独立合规风控审查】",
        "critic_ok_all": "[OK] 标普500标的池  [OK] 7日内无财报  [OK] 硬风控通过",
        "critic_rejected_prefix": "[驳回]",

        # HitL Gate 审批流
        "hitl_action_prompt": "\n请确认操作 [A=通过下单, R=驳回, E=微调参数, S=跳过/返回主菜单, EXIT=退出系统]",
        "hitl_score_threshold_fail": "提示: {ticker} 的多 Agent 加权评分未达到 0.70 门槛，未生成交易提案。",
        "hitl_critic_reject": "Critic 独立审查未通过，拒绝推入审批流: {violations}",
        "hitl_adjust_contracts": "请输入调整后的期权张数",
        "hitl_adjust_option_tp": "请输入调整后的止盈权利金 (TP)",
        "hitl_adjust_option_sl": "请输入调整后的止损权利金 (SL)",
        "hitl_adjust_shares": "请输入调整后的正股股数",
        "hitl_adjust_stock_tp": "请输入调整后的止盈价 (TP)",
        "hitl_adjust_stock_sl": "请输入调整后的止损价 (SL)",
        "hitl_param_error": "输入参数格式有误，取消本次下单。",
        "hitl_rejected_msg": "操作员已驳回该提案，已记入审计追踪。",
        "hitl_skipped_msg": "已跳过当前提案。",
        "sgov_freed_msg": "已从 SGOV 国债理财自动变现释放约 ${amount:,.2f} 现金",
        "sgov_no_pos_msg": "提示: SGOV 暂无可用持仓变现，正在检查账户总购买力...",
        "buying_power_error": "❌ 购买力不足拦截: 本次下单需 ${needed:,.2f}，当前账户可用购买力仅 ${available:,.2f}。\n【原因提示】若当前处于非美股常规交易时段 (休市中)，SGOV 变现单需等待开盘撮合成交后方能释放购买力。",
        "risk_passed_option": "[√] 硬风控通过！正在向 Alpaca 下发期权限价单: 买入 {contracts} 张 {symbol} @ ${premium:.2f}...",
        "order_submitted_success_option": "[成功] 期权订单已成功提交至 Alpaca Paper API！订单编号: {order_id}",
        "risk_passed_stock": "[√] 确定性硬风控校验通过！正在向 Alpaca 下发正股 Bracket OCO 订单...",
        "order_submitted_success_stock": "[成功] 正股订单已成功提交至 Alpaca Paper API！订单编号: {order_id}",
        "risk_rejected": "[!] 硬风控拦截，订单被拒绝: {violations}",
        "idle_cash_swept_msg": "💰 [闲置资金清扫] 剩余现金已自动买入 {symbol} {shares} 股 (年化收益率 ~4.5%)",
        "next_round_prompt": "按 Enter 键继续下一轮交易决策",
        
        # 持仓表格与菜单
        "pos_table_title": "当前持仓详情 (Live Positions)",
        "col_idx": "序号",
        "col_symbol": "标的代码",
        "pos_summary": "汇总",
        "pos_count": "{count}笔",
        "col_asset_class": "标的类型",
        "col_side": "多空",
        "col_shares": "持仓数量",
        "col_avg_price": "持仓成本均价",
        "col_curr_price": "最新市价",
        "col_mkt_val": "持仓总市值",
        "col_today_chg": "当日涨跌",
        "col_unrealized_pl": "未实现盈亏 ($)",
        "col_unrealized_plpc": "未实现盈亏 (%)",
        "no_positions": "暂无持仓",
        "asset_option": "期权",
        "asset_treasury": "国债ETF",
        "asset_equity": "正股",
        "asset_spread": "期权价差",
        "side_long": "多头",
        "side_short": "空头",
        "pos_menu_title": "【持仓交互菜单】",
        "pos_menu_prompt": "请输入要平仓/卖出的持仓 序号 或 标的代码 (输入 'Q'/Enter 返回主菜单)",
        "pos_not_found": "❌ 未找到对应持仓: '{choice}'，请检查输入！",
        "pos_qty_zero": "❌ 标的 {symbol} 当前持仓数量为 0，无需卖出。",
        "pos_selected_info": ">>> 选中持仓: {symbol} | 持有: {qty} 股 | 均价: ${avg:.2f} | 现价: ${curr:.2f} | 未实现盈亏: {pl}",
        "sell_qty_prompt": "请输入卖出股数 (输入 'ALL' 全部卖出 [默认], 'C' 取消) [当前持仓: {qty}]",
        "sell_canceled": "已取消本次卖出操作。",
        "sell_confirm_prompt": "⚠️  请确认: 是否立即向 Alpaca 提交市价卖出 {qty} 股 {symbol}？",
        "sell_success": "✅ 卖出指令已成功提交！标的: {symbol} x {qty} 股",
        "sell_failed": "❌ 卖出操作失败: {error}",
        "sell_locked_warning": "⚠️  检测到标的 {symbol} 的持仓正被未成交挂单锁定 (held_for_orders)。",
        "sell_auto_unlock_confirm": "是否自动撤销 {symbol} 的所有关联未成交挂单并重新提交卖出？",
        "sell_canceling_orders": "[*] 正在撤销 {symbol} 的活动挂单以解锁可用数量...",
        "sell_canceled_and_reselling": "✅ 已成功撤销 {count} 笔挂单，持仓已解锁！准备重新下发卖出...",
        
        # 挂单表格与菜单
        "orders_table_title": "当前未成交活动订单 (Open Orders)",
        "col_order_id": "订单ID",
        "col_order_side": "买卖",
        "col_order_type": "类型",
        "col_filled_qty": "成交/委托",
        "col_price_trigger": "价格 / 触发条件",
        "col_structure": "结构",
        "col_status": "状态",
        "col_tif": "有效期",
        "col_submitted": "提交时间",
        "no_open_orders": "暂无未成交订单",
        "order_buy": "买入",
        "order_sell": "卖出",
        "price_limit_prefix": "限: $",
        "price_stop_prefix": "止损: $",
        "price_market": "市价 (Market)",
        "order_menu_title": "【未成交挂单管理菜单】",
        "order_menu_prompt": "请输入要撤销的 序号, 标的代码 (如 'NVDA'), 或 'ALL' 撤销全部 (输入 'Q'/Enter 返回主菜单)",
        "cancel_all_confirm": "⚠️  高危操作: 确认撤销账户中所有未成交活动挂单吗？",
        "cancel_all_success": "✅ 已成功向 Alpaca 发送全量撤单请求！",
        "cancel_single_confirm": "确认撤销第 {idx} 号订单 ({symbol} {type}, ID: {id}) 吗？",
        "cancel_single_success": "✅ 已成功撤销第 {idx} 号挂单 ({symbol})！",
        "cancel_symbol_confirm": "确认撤销标的 {symbol} 的全部 {count} 笔未成交挂单吗？",
        "cancel_symbol_success": "✅ 已成功撤销标的 {symbol} 的 {count} 笔挂单！",
        "order_not_found": "❌ 未找到对应序号或标的的活动挂单: '{choice}'",

        # 扫盘看板
        "scanner_table_title": "市场全标的智能扫盘推荐矩阵 (Regime: {regime})",
        "col_sc_idx": "排名",
        "col_sc_sym": "标的代码",
        "col_sc_status": "持仓/挂单状态",
        "col_sc_sector": "所属板块",
        "col_sc_asset": "推荐资产",
        "col_sc_score": "共识评分",
        "col_sc_price": "参考现价",
        "col_sc_tp": "建议止盈 (TP)",
        "col_sc_sl": "建议止损 (SL)",
        "col_sc_rr": "盈亏比",
        "col_sc_rationale": "核心决策逻辑",
        "sc_no_results": "全市场扫描完成，暂无满足评分阈值的推荐标的",
        "status_held_order": "已持仓+挂单中",
        "status_held": "已有持仓",
        "status_ordered": "挂单中",
        "status_new": "全新机会",
    },
    LANG_EN: {
        # General & System
        "app_title": "AiAgentForTrading Interactive Quantitative Trading Terminal",
        "connecting_alpaca": "[*] Synchronizing live account portfolio and orders from Alpaca...",
        "scanning_market": "[*] Launching 5-Agent debate scan across {count} assets (Regime: {regime})...",
        "macro_status_title": "Account & Macro Status Overview",
        "col_equity": "Total Equity",
        "col_buying_power": "Buying Power",
        "col_cash": "Cash Balance",
        "col_sgov": "Treasury (SGOV)",
        "col_day_pnl": "Day P&L %",
        "col_vix": "VIX",
        "col_hy_spread": "HY Spread",
        "col_regime": "Macro Regime",
        "fetching_universe": "[*] Fetching market snapshots for {count} universe assets...",
        "universe_table_title": "S&P 500 Core Asset Pool",
        "col_u_idx": "Idx",
        "col_u_ticker": "Ticker",
        "col_u_price": "Price",
        "col_u_chg": "Change %",
        "col_u_rsi": "RSI (14D)",
        "col_u_vol": "Volume",
        "main_prompt": "Enter Ticker or Index to analyze (Enter 'S'=Scan, 'P'=Positions, 'O'=Orders, 'L'/'EN'/'ZH'=Switch Lang, 'exit'/'q'=Quit)",
        "exit_success": "Exited trading system. Happy investing!",
        "language_switched": "Language switched successfully!",
        "lang_switched_zh": "界面语言已切换为: 简体中文 (Chinese)",
        "lang_switched_en": "Language switched to: English (英文)",
        "scanner_quick_prompt": "Enter recommended item Index or Ticker to start decision (Press Enter for main menu)",
        "press_enter_back": "Press Enter to return to main menu",
        "press_enter_refresh": "Press Enter to refresh list",
        "press_enter_continue": "Press Enter to continue",
        "invalid_ticker": "Error: Symbol {ticker} is not in the whitelist universe! Please re-select.",
        "trade_mode_prompt": "Select trading preference [AUTO=Smart Hybrid, EQUITY=Equity Only, OPTION=Options Only]",
        "selected_ticker_info": ">>> Selected: {ticker} (Price: ${price:.2f}, Preference: {mode})",
        "calling_agents": "[*] Triggering 5 strategy research agents for parallel debate...",

        # Investment Memo & Critic
        "memo_title": "Investment Decision Memo ({asset_type})",
        "memo_proposal_id": "Proposal ID",
        "memo_category": "Category",
        "memo_contract_symbol": "Contract",
        "memo_action": "Action",
        "memo_suggested_contracts": "Contracts",
        "memo_total_premium": "Total Premium",
        "memo_take_profit": "Take Profit",
        "memo_stop_loss": "Stop Loss",
        "memo_target_symbol": "Symbol",
        "memo_current_price": "Price",
        "memo_suggested_shares": "Suggested Shares",
        "memo_agent_debate_section": "[5-Agent Strategy Debate Evaluations]",
        "memo_consensus_score": "Consensus Weighted Score: {score:.2f} / 1.00 (Threshold: 0.70)",
        "memo_critic_section": "[Critic Compliance & Risk Audit]",
        "critic_ok_all": "[OK] S&P 500 Universe  [OK] No Earnings in 7D  [OK] Risk Limits Passed",
        "critic_rejected_prefix": "[REJECT]",

        # HitL Gate
        "hitl_action_prompt": "\nPlease confirm action [A=Approve & Submit, R=Reject, E=Edit Params, S=Skip/Menu, EXIT=Exit]",
        "hitl_score_threshold_fail": "Notice: Multi-Agent weighted score for {ticker} did not meet 0.70 threshold. No proposal generated.",
        "hitl_critic_reject": "Critic audit failed, rejected from approval flow: {violations}",
        "hitl_adjust_contracts": "Enter adjusted option contracts",
        "hitl_adjust_option_tp": "Enter adjusted Take Profit premium (TP)",
        "hitl_adjust_option_sl": "Enter adjusted Stop Loss premium (SL)",
        "hitl_adjust_shares": "Enter adjusted shares",
        "hitl_adjust_stock_tp": "Enter adjusted Take Profit price (TP)",
        "hitl_adjust_stock_sl": "Enter adjusted Stop Loss price (SL)",
        "hitl_param_error": "Invalid parameter format, canceling order submission.",
        "hitl_rejected_msg": "Operator rejected proposal, recorded in audit trail.",
        "hitl_skipped_msg": "Proposal skipped.",
        "sgov_freed_msg": "Automatically redeemed ~${amount:,.2f} cash from SGOV Treasury ETF",
        "sgov_no_pos_msg": "Notice: No SGOV position available for sweep, checking account buying power...",
        "buying_power_error": "❌ Insufficient Buying Power: Order requires ${needed:,.2f}, available BP is ${available:,.2f}.\n[Note] If market is closed, SGOV redemption will execute at market open to free BP.",
        "risk_passed_option": "[√] Risk Guard passed! Submitting option limit order: Buy {contracts} contracts {symbol} @ ${premium:.2f}...",
        "order_submitted_success_option": "[SUCCESS] Option order successfully submitted to Alpaca Paper API! Order ID: {order_id}",
        "risk_passed_stock": "[√] Deterministic Risk Guard passed! Submitting equity Bracket OCO order to Alpaca...",
        "order_submitted_success_stock": "[SUCCESS] Equity order successfully submitted to Alpaca Paper API! Order ID: {order_id}",
        "risk_rejected": "[!] Risk Guard intercept, order rejected: {violations}",
        "idle_cash_swept_msg": "💰 [Idle Cash Sweep] Remaining cash automatically invested in {symbol} ({shares} shares, ~4.5% p.a.)",
        "next_round_prompt": "Press Enter to continue to next trading decision",

        # Positions Table & Menu
        "pos_table_title": "Live Positions Detail",
        "col_idx": "No.",
        "col_symbol": "Symbol",
        "pos_summary": "Total",
        "pos_count": "{count} items",
        "col_asset_class": "Type",
        "col_side": "Side",
        "col_shares": "Qty",
        "col_avg_price": "Avg Price",
        "col_curr_price": "Current Price",
        "col_mkt_val": "Market Value",
        "col_today_chg": "Today Chg",
        "col_unrealized_pl": "Unrealized P&L ($)",
        "col_unrealized_plpc": "Unrealized P&L (%)",
        "no_positions": "No open stock or options positions found.",
        "asset_option": "Option",
        "asset_treasury": "Treasury ETF",
        "asset_equity": "Equity",
        "asset_spread": "Option Spread",
        "side_long": "Long",
        "side_short": "Short",
        "pos_menu_title": "[Position Management Menu]",
        "pos_menu_prompt": "Enter Index or Ticker to close/sell (Enter 'Q'/Enter to return)",
        "pos_not_found": "❌ Position not found: '{choice}', please check your input!",
        "pos_qty_zero": "❌ Position quantity for {symbol} is 0.",
        "pos_selected_info": ">>> Selected: {symbol} | Qty: {qty} | Avg: ${avg:.2f} | Price: ${curr:.2f} | Unrealized P&L: {pl}",
        "sell_qty_prompt": "Enter shares to sell ('ALL' for all [default], 'C' to cancel) [Holding: {qty}]",
        "sell_canceled": "Sell order canceled.",
        "sell_confirm_prompt": "⚠️  Confirm: Submit market order to sell {qty} shares of {symbol} to Alpaca?",
        "sell_success": "✅ Sell order submitted! Symbol: {symbol} x {qty} shares",
        "sell_failed": "❌ Sell failed: {error}",
        "sell_locked_warning": "⚠️  Positions for {symbol} are locked by open orders (held_for_orders).",
        "sell_auto_unlock_confirm": "Automatically cancel open orders for {symbol} and resubmit sell order?",
        "sell_canceling_orders": "[*] Canceling open orders for {symbol} to unlock shares...",
        "sell_canceled_and_reselling": "✅ Canceled {count} order(s), shares unlocked! Resubmitting sell...",

        # Orders Table & Menu
        "orders_table_title": "Current Open Orders",
        "col_order_id": "Order ID",
        "col_order_side": "Side",
        "col_order_type": "Type",
        "col_filled_qty": "Filled/Qty",
        "col_price_trigger": "Price / Trigger",
        "col_structure": "Structure",
        "col_status": "Status",
        "col_tif": "TIF",
        "col_submitted": "Submitted At",
        "no_open_orders": "No open orders found.",
        "order_buy": "Buy",
        "order_sell": "Sell",
        "price_limit_prefix": "Lim: $",
        "price_stop_prefix": "Stop: $",
        "price_market": "Market",
        "order_menu_title": "[Open Orders Management Menu]",
        "order_menu_prompt": "Enter Index, Symbol (e.g. 'NVDA'), or 'ALL' to cancel (Enter 'Q'/Enter to return)",
        "cancel_all_confirm": "⚠️  High Risk: Cancel all open orders in the account?",
        "cancel_all_success": "✅ Sent cancel all orders request to Alpaca!",
        "cancel_single_confirm": "Cancel order #{idx} ({symbol} {type}, ID: {id})?",
        "cancel_single_success": "✅ Successfully canceled order #{idx} ({symbol})!",
        "cancel_symbol_confirm": "Cancel all {count} open orders for {symbol}?",
        "cancel_symbol_success": "✅ Canceled {count} order(s) for {symbol}!",
        "order_not_found": "❌ No open orders matched: '{choice}'",

        # Scanner Table
        "scanner_table_title": "Market Scan Recommendation Matrix (Regime: {regime})",
        "col_sc_idx": "Rank",
        "col_sc_sym": "Symbol",
        "col_sc_status": "Status",
        "col_sc_sector": "Sector",
        "col_sc_asset": "Asset",
        "col_sc_score": "Consensus Score",
        "col_sc_price": "Price",
        "col_sc_tp": "Target (TP)",
        "col_sc_sl": "Stop (SL)",
        "col_sc_rr": "R:R",
        "col_sc_rationale": "Decision Rationale",
        "sc_no_results": "Market scan completed, no assets met threshold.",
        "status_held_order": "Held + Ordered",
        "status_held": "Held",
        "status_ordered": "Ordered",
        "status_new": "New Opportunity",
    }
}


def get_current_lang() -> str:
    """获取当前语言代码 ('zh' 或 'en')"""
    return _CURRENT_LANG


def set_current_lang(lang: str) -> None:
    """设置当前语言 ('zh' 或 'en')"""
    global _CURRENT_LANG
    if lang in [LANG_ZH, LANG_EN]:
        _CURRENT_LANG = lang


def toggle_lang() -> str:
    """在中英文之间切换并返回切换后的语言代码"""
    global _CURRENT_LANG
    _CURRENT_LANG = LANG_EN if _CURRENT_LANG == LANG_ZH else LANG_ZH
    return _CURRENT_LANG


def t(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    根据指定语言或当前全局语言获取翻译文本，支持动态变量插值。
    若找不到 key，则回退到当前语言对应模板或 key 本身。
    """
    target_lang = lang if lang in [LANG_ZH, LANG_EN] else _CURRENT_LANG
    lang_dict = TRANSLATIONS.get(target_lang, TRANSLATIONS[LANG_ZH])
    template = lang_dict.get(key)
    if template is None:
        template = TRANSLATIONS[LANG_ZH].get(key, key)
    
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
