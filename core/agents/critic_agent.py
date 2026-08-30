import yaml
from typing import Dict, Any, List, Tuple

class CriticAgent:
    """ 审核智能体：仅对照底线规则进行合规校验，不预测盈利能力 """

    def __init__(self, config_path: str = "config/investment_memo.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f).get("critic_rules", {})

    def audit(self, proposal: Dict[str, Any], sp500_whitelist: List[str], days_to_earnings: int) -> Tuple[bool, List[str]]:
        violations = []

        # 1. 标普 500 白名单校验
        if proposal.get("ticker") not in sp500_whitelist:
            violations.append(f"标的 {proposal.get('ticker')} 不在 S&P 500 白名单中")

        # 2. 7 天二元财报事件避让
        if days_to_earnings <= self.rules.get("earnings_blackout_days", 7):
            violations.append(f"距离财报发布仅剩 {days_to_earnings} 天 (需规避 7 天内二元事件)")

        # 3. 仓位比例上限 (< 10%)
        if proposal.get("position_pct", 0.0) > self.rules.get("max_single_position_pct", 0.10):
            violations.append(f"建议单仓比例超限: {proposal.get('position_pct'):.1%} > 10.0%")

        # 4. 杠杆率校验
        if proposal.get("leverage", 1.0) > self.rules.get("max_leverage", 1.0):
            violations.append(f"杠杆率超限: {proposal.get('leverage')} > 1.0x")

        # 5. 必备字段完整性校验
        for field in self.rules.get("required_fields", []):
            if field not in proposal or proposal[field] is None:
                violations.append(f"缺少必要字段: {field}")

        return (len(violations) == 0, violations)