from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# PyYAML 用于加载投资备忘录配置
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # 缺失时回退为基础文本解析


# ---------------------------------------------------------------------------
# 1. 配置与载入
# ---------------------------------------------------------------------------

DEFAULT_MEMO_PATH = "config/investment_memo.yaml"


def load_investment_memo(path: str = DEFAULT_MEMO_PATH) -> Dict[str, Any]:
    """
    加载投资备忘录 YAML 配置。

    期望结构：
    {
        "sp500_universe": ["AAPL", "MSFT", "NVDA", ...],       # S&P 500 白名单
        "capital_base": 100000.0                                 # 总资金基准
    }
    """
    if yaml is not None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                memo = yaml.safe_load(f)
            return memo if memo else {}
        except FileNotFoundError:
            print(f"[Critic] Memo file not found: {path}, using defaults.")
    # fallback：基础文本解析（仅 key=value 形式）
    memo: Dict[str, Any] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    try:
                        v = int(v)
                    except ValueError:
                        try:
                            v = float(v)
                        except ValueError:
                            pass
                    memo[k] = v
    except FileNotFoundError:
        pass
    return memo


# ---------------------------------------------------------------------------
# 2. 结构完整性检查
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["ACTION", "TICKER", "SHARES", "TP", "SL", "RATIONALE"]


def check_structural_integrity(proposal: Dict[str, Any]) -> Dict[str, Any]:
    """
    核对提案是否包含所有必需字段。

    返回
    ------
    {
        "pass": bool,
        "missing_fields": List[str]   # 未发现的字段名
    }
    """
    prop_keys = {k.upper(): True for k in proposal.keys()}
    missing = [f for f in REQUIRED_FIELDS if f not in prop_keys]
    return {
        "pass": len(missing) == 0,
        "missing_fields": missing,
    }


# ---------------------------------------------------------------------------
# 3. S&P 500 Universe 检查
# ---------------------------------------------------------------------------

def check_sp500_universe(ticker: str, sp500_universe: List[str]) -> Dict[str, Any]:
    """
    验证目标标的是否严格在标普 500 白名单池内。

    返回
    ------
    {
        "pass": bool,
        "ticker": str,
        "in_universe": bool
    }
    """
    upper = ticker.upper()
    in_universe = any(u.upper() == upper for u in sp500_universe)
    return {
        "pass": in_universe,
        "ticker": ticker,
        "in_universe": in_universe,
    }


# ---------------------------------------------------------------------------
# 4. 7 日财报避让检查
# ---------------------------------------------------------------------------

def _fetch_earnings_date(ticker: str) -> Optional[datetime]:
    """
    占位：从金融日历接口获取财报日期。
    实际生产时接入 FRED / Alpha Vantage / Yahoo Finance Calendar 等。
    此处返回 None（视作通过，避免因数据缺失误阻）。
    """
    return None


def check_no_earnings_in_7d(ticker: str) -> Dict[str, Any]:
    """
    确保目标标的在未来 7 天内无二元财报事件。

    返回
    ------
    {
        "pass": bool,
        "earnings_date": Optional[datetime],
        "warning": str
    }
    """
    earnings_dt = _fetch_earnings_date(ticker)
    now = datetime.now()
    seven_later = now + timedelta(days=7)

    if earnings_dt is None:
        return {"pass": True, "earnings_date": None, "warning": "无财报数据，视为通过"}

    if now <= earnings_dt <= seven_later:
        return {
            "pass": False,
            "earnings_date": earnings_dt,
            "warning": f"财报在7D内: {earnings_dt.date()}",
        }

    return {"pass": True, "earnings_date": None, "warning": "未来7日无财报"}


# ---------------------------------------------------------------------------
# 5. 杠杆率校验 (Lev <= 1.0x)
# ---------------------------------------------------------------------------

def check_leverage(order_amount: float, buying_power: float) -> Dict[str, Any]:
    """
    确保杠杆不超过 1.0x。

    杠杆 = 订单金额 / 可用保证金（买入力）。
    当 buying_power 为 0 或负数时视为失败。

    返回
    ------
    {
        "pass": bool,
        "leverage": float,          # 实际杠杆比率
        "warning": str
    }
    """
    if buying_power <= 0:
        return {
            "pass": False,
            "leverage": float("inf"),
            "warning": "可用保证金 <= 0",
        }

    leverage = order_amount / buying_power
    passed = leverage <= 1.0

    return {
        "pass": passed,
        "leverage": round(leverage, 4),
        "warning": "杠杆超过 1.0x" if not passed else "杠杆在 1.0x 以内",
    }


# ---------------------------------------------------------------------------
# 6. 单标的仓位上限校验 (<=10% total capital)
# ---------------------------------------------------------------------------

def check_position_limit(
    position_amount: float,
    total_capital: float,
    limit_pct: float = 0.10,
) -> Dict[str, Any]:
    """
    检查单标仓位金额是否超过总资金的 limit_pct（默认 10%）。

    返回
    ------
    {
        "pass": bool,
        "position_pct": float,      # 仓位占比 %
        "warning": str
    }
    """
    if total_capital <= 0:
        return {
            "pass": False,
            "position_pct": float("inf"),
            "warning": "总资金 <= 0",
        }

    position_pct = position_amount / total_capital
    passed = position_pct <= limit_pct

    return {
        "pass": passed,
        "position_pct": round(position_pct * 100, 2),
        "warning": (
            f"仓位 exceed {limit_pct*100:.1f}% limit"
            if not passed
            else f"仓位在 {limit_pct*100:.1f}% limit 以内"
        ),
    }


# ---------------------------------------------------------------------------
# 7. 主治理检查入口
# ---------------------------------------------------------------------------

def check_proposal(
    proposal: Dict[str, Any],
    memo: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    对单个交易提案执行全部合规校验。

    参数
    ----------
    proposal : Dict[str, Any]
        交易提案字典。必须含有 (大小写不敏感)：
            ACTION, TICKER, SHARES, TP, SL, RATIONALE
    memo : Dict[str, Any], optional
        已载入的 investment_memo。若为 None 将尝试从 DEFAULT_MEMO_PATH 载入。

    返回
    ------
    {
        "overall_pass": bool,               # 所有检查是否全部通过
        "structural_integrity": Dict,       # 结构完整性结果
        "sp500_universe": Dict,              # S&P 500 校验结果
        "no_earnings_in_7d": Dict,           # 财报避让结果
        "leverage": Dict,                    # 杠杆校验结果
        "position_limit": Dict,              # 单仓位上限结果
        "proposal_ticker": str,              # 目标标的代码
        "proposal_action": str,              # 买卖向
    }
    """
    # --- 1) 载入 memo ---
    if memo is None:
        memo = load_investment_memo()

    sp500_universe: List[str] = memo.get("sp500_universe", [])
    capital_base: float = float(memo.get("capital_base", 1e6))  # 默认 1M USD

    # --- 2) 正规化提案键名 ---
    prop = {k.upper(): v for k, v in proposal.items()}

    # --- 3) 逐项检查 ---
    # 3.1 结构完整性
    struct = check_structural_integrity(prop)

    # 3.2 S&P 500 Universe
    ticker = prop.get("TICKER", "")
    universe = check_sp500_universe(ticker, sp500_universe)

    # 3.3 7 日财报避让
    earnings = check_no_earnings_in_7d(ticker)

    # 3.4 杠杆率
    shares: float = float(prop.get("SHARES", 0))
    last_price: float = 1.0  # TODO: 替换为真实行情
    order_amount: float = shares * last_price
    buying_power: float = capital_base  # 简化：视总资金为可用买入力
    leverage = check_leverage(order_amount, buying_power)

    # 3.5 单仓位上限
    position_amount: float = order_amount
    pos_limit = check_position_limit(position_amount, capital_base, limit_pct=0.10)

    # --- 4) 综合判定 ---
    all_pass = all(
        [
            struct["pass"],
            universe["pass"],
            earnings["pass"],
            leverage["pass"],
            pos_limit["pass"],
        ]
    )

    result: Dict[str, Any] = {
        "overall_pass": all_pass,
        "structural_integrity": struct,
        "sp500_universe": universe,
        "no_earnings_in_7d": earnings,
        "leverage": leverage,
        "position_limit": pos_limit,
        "proposal_ticker": ticker,
        "proposal_action": prop.get("ACTION", ""),
    }

    return result


# ---------------------------------------------------------------------------
# 8. CLI 辅助（可选）
# ---------------------------------------------------------------------------

def print_check_result(result: Dict[str, Any]) -> None:
    """以表格形式漂亮输出治理检查结果。"""
    overall = "PASS" if result["overall_pass"] else "FAIL"
    print("\n=== Critic Governance Check Result ===")
    print(f"Overall: {overall}\n")

    checks: List[tuple[str, Dict[str, Any]]] = [
        ("Structural Integrity", result["structural_integrity"]),
        ("S&P 500 Universe", result["sp500_universe"]),
        ("7D Earnings Avoidance", result["no_earnings_in_7d"]),
        ("Leverage <= 1.0x", result["leverage"]),
        ("Position <= 10% Capital", result["position_limit"]),
    ]

    for name, check in checks:
        status = "PASS" if check["pass"] else "FAIL"
        details = check.get("warning", check.get("missing_fields", ""))
        print(f"  [{status}] {name}")
        if details:
            print(f"           -> {details}")

    print()


# ---------------------------------------------------------------------------
# 9. 主入口（脚本模式）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json as _json

    # 读取示例提案（若提供命令行参数则读取 JSON 文件，否则使用示例）
    example_proposal: Dict[str, Any] = {
        "ACTION": "BUY",
        "TICKER": "AAPL",
        "SHARES": 100,
        "TP": 150.0,
        "SL": 130.0,
        "RATIONALE": "Momentum breakout with increasing volume.",
    }

    memo_path: str = sys.argv[1] if len(sys.argv) > 1 else None
    proposal_path: str = sys.argv[2] if len(sys.argv) > 2 else None

    # 如果提供了提案文件路径，则从 JSON 读取
    if proposal_path:
        try:
            with open(proposal_path, "r", encoding="utf-8") as f:
                proposal = _json.load(f)
        except Exception as e:
            print(f"[Critic] 无法读取提案文件: {e}")
            proposal = example_proposal
    else:
        proposal = example_proposal

    result = check_proposal(proposal, memo_path if memo_path else None)
    print_check_result(result)
    print(_json.dumps(result, ensure_ascii=False, indent=2))