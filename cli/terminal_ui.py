"""
cli/terminal_ui.py
终端富文本渲染面板与交互看板 (Rich Terminal UI)
支持投资备忘录 Panel、当前持仓详情 Table、未成交订单 Table 及综合账户看板
"""

from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markup import escape
from rich import box

import sys
from cli.i18n import t, get_current_lang

# Ensure UTF-8 output on Windows if possible
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()


def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全转换为 float 类型"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_get(item: Any, attr: str, default: Any = None) -> Any:
    """安全从对象或字典中获取属性或键值"""
    if isinstance(item, dict):
        return item.get(attr, default)
    return getattr(item, attr, default)


def _clean_enum_str(val: Any, default: str = "") -> str:
    """安全提取 Enum 或字符串的纯文本描述"""
    if val is None:
        return default
    if hasattr(val, "value"):
        return str(val.value).upper()
    s = str(val).strip()
    if "." in s and not s.startswith("$"):
        s = s.split(".")[-1]
    return s.upper()


def render_positions_table(positions: Optional[List[Any]] = None, lang: Optional[str] = None) -> Table:
    """
    构造当前实盘/模拟持仓详情表格 (Rich Table)
    支持正股 (US_EQUITY)、期权 (US_OPTION) 及货币/国债 ETF (SGOV 等)
    """
    table = Table(
        title=f"[bold cyan]{t('pos_table_title', lang=lang)}[/bold cyan]",
        border_style="cyan",
        header_style="bold cyan",
        show_footer=True,
        box=box.ROUNDED,
        pad_edge=False,
        padding=(0, 1),
    )

    table.add_column(t("col_idx", lang=lang), justify="center", style="dim", footer=t("pos_summary", lang=lang), min_width=4, no_wrap=True)
    table.add_column(t("col_symbol", lang=lang), justify="center", style="bold yellow", footer=t("pos_count", lang=lang, count=len(positions or [])), min_width=6, no_wrap=True)
    table.add_column(t("col_asset_class", lang=lang), justify="center", min_width=6, no_wrap=True)
    table.add_column(t("col_side", lang=lang), justify="center", min_width=4, no_wrap=True)
    table.add_column(t("col_shares", lang=lang), justify="right", style="bold", min_width=8, no_wrap=True)
    table.add_column(t("col_avg_price", lang=lang), justify="right", min_width=10, no_wrap=True)
    table.add_column(t("col_curr_price", lang=lang), justify="right", style="bold", min_width=10, no_wrap=True)
    table.add_column(t("col_mkt_val", lang=lang), justify="right", style="cyan", min_width=12, no_wrap=True)
    table.add_column(t("col_today_chg", lang=lang), justify="right", min_width=9, no_wrap=True)
    table.add_column(t("col_unrealized_pl", lang=lang), justify="right", min_width=11, no_wrap=True)
    table.add_column(t("col_unrealized_plpc", lang=lang), justify="right", min_width=9, no_wrap=True)

    if not positions:
        table.add_row("-", f"[dim]{t('no_positions', lang=lang)}[/dim]", "-", "-", "-", "-", "-", "$0.00", "-", "$0.00", "0.00%")
        return table

    total_market_value = 0.0
    total_unrealized_pl = 0.0
    total_cost_basis = 0.0

    for idx, pos in enumerate(positions, 1):
        symbol = str(_safe_get(pos, "symbol", "UNKNOWN"))
        asset_class_raw = _clean_enum_str(_safe_get(pos, "asset_class", "us_equity")).lower()
        if "option" in asset_class_raw or len(symbol) > 10:
            asset_type_str = f"[magenta]{t('asset_option', lang=lang)}[/magenta]"
        elif symbol in ["SGOV", "BIL", "SHV", "USFR"]:
            asset_type_str = f"[yellow]{t('asset_treasury', lang=lang)}[/yellow]"
        else:
            asset_type_str = f"[blue]{t('asset_equity', lang=lang)}[/blue]"

        side_raw = _clean_enum_str(_safe_get(pos, "side", "long"))
        if side_raw in ["LONG", "BUY"]:
            side_str = f"[green]{t('side_long', lang=lang)}[/green]"
        else:
            side_str = f"[red]{t('side_short', lang=lang)}[/red]"

        qty = _safe_float(_safe_get(pos, "qty", 0))
        qty_str = f"{qty:,.0f}" if qty.is_integer() else f"{qty:,.2f}"

        avg_price = _safe_float(_safe_get(pos, "avg_entry_price", 0.0))
        curr_price = _safe_float(_safe_get(pos, "current_price", 0.0))
        mkt_val = _safe_float(_safe_get(pos, "market_value", qty * curr_price))
        cost_val = _safe_float(_safe_get(pos, "cost_basis", qty * avg_price))

        unrealized_pl = _safe_float(_safe_get(pos, "unrealized_pl", mkt_val - cost_val))
        unrealized_plpc = _safe_float(_safe_get(pos, "unrealized_plpc", 0.0))
        if unrealized_plpc == 0.0 and cost_val != 0:
            unrealized_plpc = unrealized_pl / cost_val

        change_today = _safe_float(_safe_get(pos, "change_today", 0.0))

        total_market_value += mkt_val
        total_unrealized_pl += unrealized_pl
        total_cost_basis += cost_val

        # 盈亏颜色高亮 (标准化格式: +$XX.XX 或 -$XX.XX)
        pl_color = "green" if unrealized_pl >= 0 else "red"
        pl_sign = "+$" if unrealized_pl >= 0 else "-$"
        pl_str = f"[{pl_color}]{pl_sign}{abs(unrealized_pl):,.2f}[/{pl_color}]"
        
        plpc_sign = "+" if unrealized_plpc >= 0 else ""
        plpc_str = f"[{pl_color}]{plpc_sign}{unrealized_plpc * 100:.2f}%[/{pl_color}]"

        chg_color = "green" if change_today >= 0 else "red"
        chg_sign = "+" if change_today >= 0 else ""
        chg_str = f"[{chg_color}]{chg_sign}{change_today * 100:.2f}%[/{chg_color}]"

        table.add_row(
            str(idx),
            symbol,
            asset_type_str,
            side_str,
            qty_str,
            f"${avg_price:,.2f}",
            f"${curr_price:,.2f}",
            f"${mkt_val:,.2f}",
            chg_str,
            pl_str,
            plpc_str,
        )

    total_pl_pct = (total_unrealized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0.0
    tot_color = "green" if total_unrealized_pl >= 0 else "red"
    tot_pl_sign = "+$" if total_unrealized_pl >= 0 else "-$"
    tot_plpc_sign = "+" if total_pl_pct >= 0 else ""

    # 更新底部汇总字段
    table.columns[7].footer = f"[bold cyan]${total_market_value:,.2f}[/bold cyan]"
    table.columns[9].footer = f"[bold {tot_color}]{tot_pl_sign}{abs(total_unrealized_pl):,.2f}[/bold {tot_color}]"
    table.columns[10].footer = f"[bold {tot_color}]{tot_plpc_sign}{total_pl_pct:.2f}%[/bold {tot_color}]"

    return table


def render_open_orders_table(orders: Optional[List[Any]] = None, lang: Optional[str] = None) -> Table:
    """
    构造当前未成交活动订单表格 (Rich Table)
    包含市价单、限价单、止盈止损单及 Bracket OCO 挂单等
    """
    table = Table(
        title=f"[bold magenta]{t('orders_table_title', lang=lang)}[/bold magenta]",
        border_style="magenta",
        header_style="bold magenta",
        show_footer=True,
        box=box.ROUNDED,
        pad_edge=False,
        padding=(0, 1),
    )

    table.add_column(t("col_idx", lang=lang), justify="center", style="dim", footer=t("pos_summary", lang=lang), min_width=4, no_wrap=True)
    table.add_column(t("col_order_id", lang=lang), justify="center", style="dim", footer=t("pos_count", lang=lang, count=len(orders or [])), min_width=8, no_wrap=True)
    table.add_column(t("col_symbol", lang=lang), justify="center", style="bold yellow", min_width=6, no_wrap=True)
    table.add_column(t("col_order_side", lang=lang), justify="center", min_width=4, no_wrap=True)
    table.add_column(t("col_order_type", lang=lang), justify="center", min_width=6, no_wrap=True)
    table.add_column(t("col_filled_qty", lang=lang), justify="right", style="bold", min_width=10, no_wrap=True)
    table.add_column(t("col_price_trigger", lang=lang), justify="left", style="cyan", min_width=20, no_wrap=True)
    table.add_column(t("col_structure", lang=lang), justify="center", min_width=6, no_wrap=True)
    table.add_column(t("col_status", lang=lang), justify="center", style="bold", min_width=6, no_wrap=True)
    table.add_column(t("col_tif", lang=lang), justify="center", style="dim", min_width=6, no_wrap=True)
    table.add_column(t("col_submitted", lang=lang), justify="center", style="dim", min_width=14, no_wrap=True)

    if not orders:
        table.add_row("-", "-", f"[dim]{t('no_open_orders', lang=lang)}[/dim]", "-", "-", "-", "-", "-", "-", "-", "-")
        return table

    for idx, ord_item in enumerate(orders, 1):
        raw_id = str(_safe_get(ord_item, "id", ""))
        order_id_short = raw_id[:8] if len(raw_id) >= 8 else raw_id

        symbol = str(_safe_get(ord_item, "symbol", "UNKNOWN"))

        side_raw = _clean_enum_str(_safe_get(ord_item, "side", "buy"))
        if "BUY" in side_raw:
            side_str = f"[bold green]{t('order_buy', lang=lang)}[/bold green]"
        else:
            side_str = f"[bold red]{t('order_sell', lang=lang)}[/bold red]"

        order_type = _clean_enum_str(_safe_get(ord_item, "order_type", _safe_get(ord_item, "type", "LIMIT")))

        qty = _safe_float(_safe_get(ord_item, "qty", 0))
        filled_qty = _safe_float(_safe_get(ord_item, "filled_qty", 0))

        qty_str = f"{qty:,.0f}" if qty.is_integer() else f"{qty:,.2f}"
        filled_str = f"{filled_qty:,.0f}" if filled_qty.is_integer() else f"{filled_qty:,.2f}"
        progress_str = f"{filled_str}/{qty_str}"

        # 价格显示
        limit_price = _safe_get(ord_item, "limit_price")
        stop_price = _safe_get(ord_item, "stop_price")
        price_parts = []
        if limit_price is not None:
            price_parts.append(f"{t('price_limit_prefix', lang=lang)}{_safe_float(limit_price):.2f}")
        if stop_price is not None:
            price_parts.append(f"{t('price_stop_prefix', lang=lang)}{_safe_float(stop_price):.2f}")
        price_display = " / ".join(price_parts) if price_parts else t("price_market", lang=lang)

        order_class = _clean_enum_str(_safe_get(ord_item, "order_class", "simple"))
        status = _clean_enum_str(_safe_get(ord_item, "status", "open"))
        tif = _clean_enum_str(_safe_get(ord_item, "time_in_force", "DAY"))

        # 时间格式化 (截取 MM-DD HH:MM:SS)
        submitted_at_raw = _safe_get(ord_item, "submitted_at", _safe_get(ord_item, "created_at", ""))
        if submitted_at_raw:
            submitted_str = str(submitted_at_raw)[5:19].replace("T", " ")
        else:
            submitted_str = "-"

        # 状态颜色高亮
        if status in ["ACCEPTED", "NEW", "OPEN"]:
            status_str = f"[cyan]{status}[/cyan]"
        elif "PARTIAL" in status:
            status_str = f"[yellow]{status}[/yellow]"
        elif status in ["FILLED", "CLOSED"]:
            status_str = f"[green]{status}[/green]"
        elif status in ["CANCELED", "REJECTED", "EXPIRED"]:
            status_str = f"[red]{status}[/red]"
        else:
            status_str = status

        table.add_row(
            str(idx),
            order_id_short,
            symbol,
            side_str,
            order_type,
            progress_str,
            price_display,
            order_class,
            status_str,
            tif,
            submitted_str,
        )

    return table


def print_positions_table(positions: Optional[List[Any]] = None, lang: Optional[str] = None) -> None:
    """直接在控制台渲染持仓详情表格"""
    console.print(render_positions_table(positions, lang=lang))


def print_open_orders_table(orders: Optional[List[Any]] = None, lang: Optional[str] = None) -> None:
    """直接在控制台渲染未成交订单表格"""
    console.print(render_open_orders_table(orders, lang=lang))


def print_portfolio_dashboard(
    positions: Optional[List[Any]] = None,
    orders: Optional[List[Any]] = None,
    lang: Optional[str] = None
) -> None:
    """组合渲染持仓与未成交活动订单看板"""
    console.print(render_positions_table(positions, lang=lang))
    console.print("\n")
    console.print(render_open_orders_table(orders, lang=lang))


def render_scanner_results_table(
    scan_results: List[Dict[str, Any]],
    current_regime: str = "Bull_Trend",
    lang: Optional[str] = None
) -> Table:
    """
    构造一键扫盘结果推荐表格 (Rich Table)
    按综合共识评分降序展示精选出的优质买入标的
    """
    table = Table(
        title=f"[bold green]{t('scanner_table_title', lang=lang, regime=current_regime)}[/bold green]",
        border_style="green",
        header_style="bold green",
        show_footer=True,
        box=box.ROUNDED,
        pad_edge=False,
        padding=(0, 1),
    )

    table.add_column(t("col_sc_idx", lang=lang), justify="center", style="dim", footer=t("pos_summary", lang=lang), min_width=4, no_wrap=True)
    table.add_column(t("col_sc_sym", lang=lang), justify="center", style="bold yellow", footer=t("pos_count", lang=lang, count=len(scan_results)), min_width=6, no_wrap=True)
    table.add_column(t("col_sc_status", lang=lang), justify="center", min_width=10, no_wrap=True)
    table.add_column(t("col_sc_sector", lang=lang), justify="center", style="dim", min_width=12, no_wrap=True)
    table.add_column(t("col_sc_asset", lang=lang), justify="center", min_width=10, no_wrap=True)
    table.add_column(t("col_sc_score", lang=lang), justify="center", style="bold", min_width=10, no_wrap=True)
    table.add_column(t("col_sc_price", lang=lang), justify="right", style="cyan", min_width=10, no_wrap=True)
    table.add_column(t("col_sc_tp", lang=lang), justify="right", style="green", min_width=12, no_wrap=True)
    table.add_column(t("col_sc_sl", lang=lang), justify="right", style="red", min_width=12, no_wrap=True)
    table.add_column(t("col_sc_rr", lang=lang), justify="center", min_width=7, no_wrap=True)
    table.add_column(t("col_sc_rationale", lang=lang), justify="left", min_width=24)

    if not scan_results:
        table.add_row("-", "-", "-", "-", "-", f"[dim]{t('sc_no_results', lang=lang)}[/dim]", "-", "-", "-", "-", "-")
        return table

    for idx, item in enumerate(scan_results, 1):
        sym = item.get("symbol", "UNKNOWN")
        sector = item.get("sector", "General")
        score = float(item.get("score", 0.0))
        price = float(item.get("price", 0.0))
        status_tag = item.get("status_tag", "NEW")
        asset_mode = item.get("recommended_asset", "EQUITY")
        tp_price = float(item.get("take_profit_price", price * 1.08))
        sl_price = float(item.get("stop_loss_price", price * 0.96))
        rr = float(item.get("risk_reward_ratio", 2.0))
        rationale = item.get("rationale", "-")

        # 状态颜色高亮区分 (已持仓 / 挂单中 / 全新机会)
        if status_tag == "HELD_ORDER":
            status_str = f"[bold magenta]{t('status_held_order', lang=lang)}[/bold magenta]"
        elif status_tag == "HELD":
            status_str = f"[bold magenta]{t('status_held', lang=lang)}[/bold magenta]"
        elif status_tag == "ORDERED":
            status_str = f"[bold yellow]{t('status_ordered', lang=lang)}[/bold yellow]"
        else:
            status_str = f"[bold green]{t('status_new', lang=lang)}[/bold green]"

        # 资产高亮
        if "SPREAD" in asset_mode or "OPTION" in asset_mode:
            asset_str = f"[magenta]{t('asset_spread', lang=lang)}[/magenta]"
        else:
            asset_str = f"[blue]{t('asset_equity', lang=lang)}[/blue]"

        # 评分高亮 (>= 0.85 亮绿, >= 0.70 浅绿, 其余黄色)
        if score >= 0.85:
            score_str = f"[bold green]{score:.2f} ⭐[/bold green]"
        elif score >= 0.70:
            score_str = f"[green]{score:.2f}[/green]"
        else:
            score_str = f"[yellow]{score:.2f}[/yellow]"

        table.add_row(
            str(idx),
            sym,
            status_str,
            sector,
            asset_str,
            score_str,
            f"${price:,.2f}",
            f"${tp_price:,.2f} (+8%)",
            f"${sl_price:,.2f} (-4%)",
            f"{rr:.1f}:1",
            rationale,
        )

    return table


def print_scanner_results(
    scan_results: List[Dict[str, Any]],
    current_regime: str = "Bull_Trend",
    lang: Optional[str] = None
) -> None:
    """直接在控制台打印扫盘推荐表格"""
    console.print(render_scanner_results_table(scan_results, current_regime, lang=lang))


def render_hybrid_memo_panel(memo, critic_passed: bool, violations: list, lang: Optional[str] = None):
    """渲染多智能体投资决策备忘录 Panel"""
    eval_lines = []
    for e in memo.agent_evaluations:
        escaped_rationale = escape(str(e.rationale))
        eval_lines.append(f"• [bold green]【{e.agent_name}】[/bold green] (Score: {e.score:.2f})\n  {escaped_rationale}")

    eval_text = "\n\n".join(eval_lines)
    critic_status = (
        f"[bold green]{t('critic_ok_all', lang=lang)}[/bold green]"
        if critic_passed
        else f"[bold red]{t('critic_rejected_prefix', lang=lang)} {escape('; '.join(violations))}[/bold red]"
    )

    asset_type = getattr(memo, "asset_type", "EQUITY")
    if asset_type == "OPTION":
        header = f"""[bold cyan]{t('memo_proposal_id', lang=lang)}:[/bold cyan] {memo.proposal_id} | [bold magenta]{t('memo_category', lang=lang)}: OPTION (Standard {memo.option_type})[/bold magenta]
[bold cyan]{t('memo_contract_symbol', lang=lang)}:[/bold cyan] {memo.contract_symbol} (Exp: {memo.expiration_date}, Strike: ${memo.strike_price:.2f}, DTE: {memo.dte}D)
[bold cyan]{t('memo_action', lang=lang)}:[/bold cyan] {memo.action} | [bold cyan]{t('memo_suggested_contracts', lang=lang)}:[/bold cyan] {memo.suggested_contracts} (Premium: ${memo.premium_per_share:.2f})
[bold cyan]{t('memo_total_premium', lang=lang)}:[/bold cyan] ${memo.total_premium:.2f} ({memo.cost_pct:.2%}) | [bold cyan]Greeks:[/bold cyan] Delta {memo.delta} | Theta {memo.theta} | IV {memo.iv:.1%}
[bold cyan]{t('memo_take_profit', lang=lang)}:[/bold cyan] ${memo.take_profit_price:.2f} (+50.0%) | [bold cyan]{t('memo_stop_loss', lang=lang)}:[/bold cyan] ${memo.stop_loss_price:.2f} (-30.0%)"""
    else:
        stock_amount = getattr(memo, "stock_total_amount", None) or getattr(memo, "total_amount", 0.0)
        curr_price = getattr(memo, "current_underlying_price", None) or getattr(memo, "current_price", 0.0)
        ticker_name = getattr(memo, "underlying_ticker", None) or getattr(memo, "ticker", "")
        header = f"""[bold cyan]{t('memo_proposal_id', lang=lang)}:[/bold cyan] {memo.proposal_id} | [bold green]{t('memo_category', lang=lang)}: EQUITY (Common Stock)[/bold green]
[bold cyan]{t('memo_target_symbol', lang=lang)}:[/bold cyan] {ticker_name} | [bold cyan]{t('memo_current_price', lang=lang)}:[/bold cyan] ${curr_price:.2f} | [bold cyan]{t('memo_suggested_shares', lang=lang)}:[/bold cyan] {memo.suggested_shares} shares (${stock_amount:.2f})
[bold cyan]{t('memo_take_profit', lang=lang)}:[/bold cyan] ${memo.take_profit_price:.2f} (+8.0%) | [bold cyan]{t('memo_stop_loss', lang=lang)}:[/bold cyan] ${memo.stop_loss_price:.2f} (-4.0%)"""

    content = f"""{header}
────────────────────────────────────────────────────────────────────────────────
[bold yellow]{t('memo_agent_debate_section', lang=lang)}[/bold yellow]
{eval_text}

[bold magenta]{t('memo_consensus_score', lang=lang, score=memo.consensus_score)}[/bold magenta]
────────────────────────────────────────────────────────────────────────────────
[bold yellow]{t('memo_critic_section', lang=lang)}[/bold yellow]
{critic_status}"""

    console.print(Panel(content, title=t("memo_title", lang=lang, asset_type=asset_type), border_style="blue", expand=False))


# 别名兼容
render_memo_panel = render_hybrid_memo_panel


if __name__ == "__main__":
    # 模块独立演示
    demo_positions = [
        {
            "symbol": "AAPL",
            "asset_class": "us_equity",
            "side": "long",
            "qty": 50,
            "avg_entry_price": 220.00,
            "current_price": 232.50,
            "market_value": 11625.00,
            "cost_basis": 11000.00,
            "unrealized_pl": 625.00,
            "unrealized_plpc": 0.0568,
            "change_today": 0.0145,
        },
        {
            "symbol": "NVDA260918C00130000",
            "asset_class": "us_option",
            "side": "long",
            "qty": 2,
            "avg_entry_price": 8.50,
            "current_price": 10.20,
            "market_value": 2040.00,
            "cost_basis": 1700.00,
            "unrealized_pl": 340.00,
            "unrealized_plpc": 0.2000,
            "change_today": 0.0850,
        },
        {
            "symbol": "SGOV",
            "asset_class": "us_equity",
            "side": "long",
            "qty": 100,
            "avg_entry_price": 100.45,
            "current_price": 100.52,
            "market_value": 10052.00,
            "cost_basis": 10045.00,
            "unrealized_pl": 7.00,
            "unrealized_plpc": 0.0007,
            "change_today": 0.0001,
        },
    ]

    demo_orders = [
        {
            "id": "ord-883a91b2c4e5",
            "symbol": "MSFT",
            "side": "buy",
            "order_type": "limit",
            "qty": 20,
            "filled_qty": 0,
            "limit_price": 415.00,
            "stop_price": None,
            "order_class": "bracket",
            "status": "accepted",
            "time_in_force": "day",
            "submitted_at": "2026-09-01T14:30:00Z",
        },
        {
            "id": "ord-12ff09e871cd",
            "symbol": "TSLA",
            "side": "buy",
            "order_type": "stop_limit",
            "qty": 10,
            "filled_qty": 0,
            "limit_price": 210.00,
            "stop_price": 208.50,
            "order_class": "simple",
            "status": "new",
            "time_in_force": "gtc",
            "submitted_at": "2026-09-01T15:10:22Z",
        }
    ]

    console.print("\n[bold green]>>> 演示: 持仓详情与未成交订单面板 <<<[/bold green]\n")
    print_portfolio_dashboard(demo_positions, demo_orders)