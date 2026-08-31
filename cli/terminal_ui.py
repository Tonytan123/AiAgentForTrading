from rich.console import Console
from rich.panel import Panel
from rich.markup import escape

console = Console()


def render_hybrid_memo_panel(memo, critic_passed: bool, violations: list):
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