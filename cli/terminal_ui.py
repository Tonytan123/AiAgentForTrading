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

import sys

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


def render_positions_table(positions: Optional[List[Any]] = None) -> Table:
    """
    构造当前实盘/模拟持仓详情表格 (Rich Table)
    支持正股 (US_EQUITY)、期权 (US_OPTION) 及货币/国债 ETF (SGOV 等)
    """
    table = Table(
        title="[bold cyan]【当前实盘 / 模拟持仓详情 (Open Positions)】[/bold cyan]",
        border_style="cyan",
        header_style="bold cyan",
        show_footer=True,
    )

    table.add_column("序号", justify="center", style="dim", footer="汇总")
    table.add_column("标的代码", justify="center", style="bold yellow", footer=f"共 {len(positions or [])} 笔持仓")
    table.add_column("资产类别", justify="center")
    table.add_column("方向", justify="center")
    table.add_column("持仓数量", justify="right", style="bold")
    table.add_column("持仓均价", justify="right")
    table.add_column("当前市价", justify="right", style="bold")
    table.add_column("持仓市值", justify="right", style="cyan")
    table.add_column("当日涨跌", justify="right")
    table.add_column("浮动盈亏 ($)", justify="right")
    table.add_column("盈亏比例 (%)", justify="right")

    if not positions:
        table.add_row("-", "[dim]暂无持仓 (No Open Positions)[/dim]", "-", "-", "-", "-", "-", "$0.00", "-", "$0.00", "0.00%")
        return table

    total_market_value = 0.0
    total_unrealized_pl = 0.0
    total_cost_basis = 0.0

    for idx, pos in enumerate(positions, 1):
        symbol = str(_safe_get(pos, "symbol", "UNKNOWN"))
        asset_class_raw = _clean_enum_str(_safe_get(pos, "asset_class", "us_equity")).lower()
        if "option" in asset_class_raw or len(symbol) > 10:
            asset_type_str = "[magenta]期权[/magenta]"
        elif symbol in ["SGOV", "BIL", "SHV", "USFR"]:
            asset_type_str = "[yellow]国债ETF[/yellow]"
        else:
            asset_type_str = "[blue]正股[/blue]"

        side_raw = _clean_enum_str(_safe_get(pos, "side", "long"))
        if side_raw in ["LONG", "BUY"]:
            side_str = "[green]多 (LONG)[/green]"
        else:
            side_str = "[red]空 (SHORT)[/red]"

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

        # 盈亏颜色高亮
        pl_color = "green" if unrealized_pl >= 0 else "red"
        pl_str = f"[{pl_color}]{'+' if unrealized_pl >= 0 else ''}${unrealized_pl:,.2f}[/{pl_color}]"
        plpc_str = f"[{pl_color}]{'+' if unrealized_plpc >= 0 else ''}{unrealized_plpc * 100:.2f}%[/{pl_color}]"

        chg_color = "green" if change_today >= 0 else "red"
        chg_str = f"[{chg_color}]{'+' if change_today >= 0 else ''}{change_today * 100:.2f}%[/{chg_color}]"

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

    # 更新底部汇总字段
    table.columns[7].footer = f"[bold cyan]${total_market_value:,.2f}[/bold cyan]"
    table.columns[9].footer = f"[bold {tot_color}]{'+' if total_unrealized_pl >= 0 else ''}${total_unrealized_pl:,.2f}[/bold {tot_color}]"
    table.columns[10].footer = f"[bold {tot_color}]{'+' if total_pl_pct >= 0 else ''}{total_pl_pct:.2f}%[/bold {tot_color}]"

    return table


def render_open_orders_table(orders: Optional[List[Any]] = None) -> Table:
    """
    构造当前未成交活动订单表格 (Rich Table)
    包含市价单、限价单、止盈止损单及 Bracket OCO 挂单等
    """
    table = Table(
        title="[bold magenta]【当前未成交活动订单 (Open Orders)】[/bold magenta]",
        border_style="magenta",
        header_style="bold magenta",
        show_footer=True,
    )

    table.add_column("序号", justify="center", style="dim", footer="汇总")
    table.add_column("订单编号", justify="center", style="dim", footer=f"共 {len(orders or [])} 笔挂单")
    table.add_column("标的代码", justify="center", style="bold yellow")
    table.add_column("买卖方向", justify="center")
    table.add_column("订单类型", justify="center")
    table.add_column("委托数量", justify="right")
    table.add_column("已成交", justify="right", style="dim")
    table.add_column("未成交", justify="right", style="bold")
    table.add_column("委托价 / 触发价", justify="right", style="cyan")
    table.add_column("订单分类", justify="center")
    table.add_column("状态", justify="center", style="bold")
    table.add_column("有效期", justify="center", style="dim")
    table.add_column("提交时间", justify="center", style="dim")

    if not orders:
        table.add_row("-", "-", "[dim]暂无未成交订单 (No Open Orders)[/dim]", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-")
        return table

    for idx, ord_item in enumerate(orders, 1):
        raw_id = str(_safe_get(ord_item, "id", ""))
        order_id_short = raw_id[:8] + "..." if len(raw_id) > 10 else raw_id

        symbol = str(_safe_get(ord_item, "symbol", "UNKNOWN"))

        side_raw = _clean_enum_str(_safe_get(ord_item, "side", "buy"))
        if "BUY" in side_raw:
            side_str = "[bold green]买入 (BUY)[/bold green]"
        else:
            side_str = "[bold red]卖出 (SELL)[/bold red]"

        order_type = _clean_enum_str(_safe_get(ord_item, "order_type", _safe_get(ord_item, "type", "LIMIT")))

        qty = _safe_float(_safe_get(ord_item, "qty", 0))
        filled_qty = _safe_float(_safe_get(ord_item, "filled_qty", 0))
        unfilled_qty = max(0.0, qty - filled_qty)

        qty_str = f"{qty:,.0f}" if qty.is_integer() else f"{qty:,.2f}"
        filled_str = f"{filled_qty:,.0f}" if filled_qty.is_integer() else f"{filled_qty:,.2f}"
        unfilled_str = f"{unfilled_qty:,.0f}" if unfilled_qty.is_integer() else f"{unfilled_qty:,.2f}"

        # 价格显示
        limit_price = _safe_get(ord_item, "limit_price")
        stop_price = _safe_get(ord_item, "stop_price")
        price_parts = []
        if limit_price is not None:
            price_parts.append(f"限价: ${_safe_float(limit_price):.2f}")
        if stop_price is not None:
            price_parts.append(f"止损: ${_safe_float(stop_price):.2f}")
        price_display = " / ".join(price_parts) if price_parts else "市价 (MKT)"

        order_class = _clean_enum_str(_safe_get(ord_item, "order_class", "simple"))
        status = _clean_enum_str(_safe_get(ord_item, "status", "open"))
        tif = _clean_enum_str(_safe_get(ord_item, "time_in_force", "DAY"))

        # 时间格式化
        submitted_at_raw = _safe_get(ord_item, "submitted_at", _safe_get(ord_item, "created_at", ""))
        submitted_str = str(submitted_at_raw)[:19].replace("T", " ") if submitted_at_raw else "-"

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
            qty_str,
            filled_str,
            unfilled_str,
            price_display,
            order_class,
            status_str,
            tif,
            submitted_str,
        )

    return table


def print_positions_table(positions: Optional[List[Any]] = None) -> None:
    """直接在控制台渲染持仓详情表格"""
    console.print(render_positions_table(positions))


def print_open_orders_table(orders: Optional[List[Any]] = None) -> None:
    """直接在控制台渲染未成交订单表格"""
    console.print(render_open_orders_table(orders))


def print_portfolio_dashboard(
    positions: Optional[List[Any]] = None,
    orders: Optional[List[Any]] = None
) -> None:
    """组合渲染持仓与未成交活动订单看板"""
    console.print(render_positions_table(positions))
    console.print("\n")
    console.print(render_open_orders_table(orders))


def render_hybrid_memo_panel(memo, critic_passed: bool, violations: list):
    """渲染多智能体投资决策备忘录 Panel"""
    eval_lines = []
    for e in memo.agent_evaluations:
        escaped_rationale = escape(str(e.rationale))
        eval_lines.append(f"• [bold green]【{e.agent_name}】[/bold green] (评分: {e.score:.2f})\n  {escaped_rationale}")

    eval_text = "\n\n".join(eval_lines)
    critic_status = (
        "[bold green][OK] S&P 500 Universe  [OK] No Earnings in 7D  [OK] Risk Limits Passed[/bold green]"
        if critic_passed
        else f"[bold red][REJECT] {escape('; '.join(violations))}[/bold red]"
    )

    if getattr(memo, "asset_type", "EQUITY") == "OPTION":
        header = f"""[bold cyan]提案编号:[/bold cyan] {memo.proposal_id} | [bold magenta]类别: OPTION (Standard {memo.option_type})[/bold magenta]
[bold cyan]合约代码:[/bold cyan] {memo.contract_symbol} (Exp: {memo.expiration_date}, Strike: ${memo.strike_price:.2f}, DTE: {memo.dte}D)
[bold cyan]建议操作:[/bold cyan] {memo.action} | [bold cyan]建议张数:[/bold cyan] {memo.suggested_contracts} 张 (单张权利金: ${memo.premium_per_share:.2f})
[bold cyan]总权利金:[/bold cyan] ${memo.total_premium:.2f} ({memo.cost_pct:.2%}) | [bold cyan]Greeks:[/bold cyan] Delta {memo.delta} | Theta {memo.theta} | IV {memo.iv:.1%}
[bold cyan]止盈 (TP):[/bold cyan] ${memo.take_profit_price:.2f} (+50.0%) | [bold cyan]止损 (SL):[/bold cyan] ${memo.stop_loss_price:.2f} (-30.0%)"""
    else:
        stock_amount = getattr(memo, "stock_total_amount", None) or getattr(memo, "total_amount", 0.0)
        curr_price = getattr(memo, "current_underlying_price", None) or getattr(memo, "current_price", 0.0)
        ticker_name = getattr(memo, "underlying_ticker", None) or getattr(memo, "ticker", "")
        header = f"""[bold cyan]提案编号:[/bold cyan] {memo.proposal_id} | [bold green]类别: EQUITY (Common Stock)[/bold green]
[bold cyan]目标标的:[/bold cyan] {ticker_name} | [bold cyan]现价:[/bold cyan] ${curr_price:.2f} | [bold cyan]建议股数:[/bold cyan] {memo.suggested_shares} 股 (${stock_amount:.2f})
[bold cyan]止盈 (TP):[/bold cyan] ${memo.take_profit_price:.2f} (+8.0%) | [bold cyan]止损 (SL):[/bold cyan] ${memo.stop_loss_price:.2f} (-4.0%)"""

    content = f"""{header}
────────────────────────────────────────────────────────────────────────────────
[bold yellow]【5 大研究智能体辩论与评分】[/bold yellow]
{eval_text}

[bold magenta]=> 加权共识得分: {memo.consensus_score:.2f} (阈值 >= 0.70)[/bold magenta]
────────────────────────────────────────────────────────────────────────────────
[bold yellow]【Critic 独立合规审查】[/bold yellow]
{critic_status}"""

    console.print(Panel(content, title=f"投资决策备忘录 ({getattr(memo, 'asset_type', 'EQUITY')})", border_style="blue", expand=False))


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