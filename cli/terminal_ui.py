from rich.console import Console
from rich.panel import Panel
from rich.markup import escape

console = Console()


def render_memo_panel(memo, critic_passed: bool, violations: list):
    eval_lines = []
    for e in memo.agent_evaluations:
        escaped_rationale = escape(str(e.rationale))
        eval_lines.append(f"• [bold green]【{e.agent_name}】[/bold green] (评分: {e.score:.2f})\n  {escaped_rationale}")

    eval_text = "\n\n".join(eval_lines)
    critic_status = (
        "[bold green][OK] S&P 500 Universe  [OK] No Earnings in 7D  [OK] Lev <= 1.0x[/bold green]"
        if critic_passed
        else f"[bold red][REJECT] {escape('; '.join(violations))}[/bold red]"
    )

    content = f"""[bold cyan]提案编号:[/bold cyan] {memo.proposal_id} | [bold cyan]标的:[/bold cyan] {memo.ticker} | [bold cyan]操作:[/bold cyan] {memo.action}
[bold cyan]现价:[/bold cyan] ${memo.current_price:.2f} | [bold cyan]建议股数:[/bold cyan] {memo.suggested_shares} 股 (${memo.total_amount:.2f})
[bold cyan]止盈 (TP):[/bold cyan] ${memo.take_profit_price:.2f} (+8.0%) | [bold cyan]止损 (SL):[/bold cyan] ${memo.stop_loss_price:.2f} (-4.0%)
────────────────────────────────────────────────────────────────────────────────
[bold yellow]【5 大研究智能体辩论观点】[/bold yellow]
{eval_text}

[bold magenta]=> 加权共识得分: {memo.consensus_score:.2f} (阈值 >= 0.70)[/bold magenta]
────────────────────────────────────────────────────────────────────────────────
[bold yellow]【Critic 独立合规审查】[/bold yellow]
{critic_status}"""

    console.print(Panel(content, title="投资决策备忘录 (INVESTMENT MEMO)", border_style="blue", expand=False))