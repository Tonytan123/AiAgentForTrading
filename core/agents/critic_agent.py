import yaml
from typing import Dict, Any, List, Tuple, Optional

class CriticAgent:
    """ 审核智能体：仅对照底线规则进行合规校验，不预测盈利能力 """

    def __init__(self, config_path: str = "config/investment_memo.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.rules = yaml.safe_load(f).get("critic_rules", {})

    def audit(
        self,
        proposal: Dict[str, Any],
        sp500_whitelist: List[str],
        days_to_earnings: int,
        asset_type: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        if asset_type is None:
            asset_type = proposal.get("asset_type", "EQUITY")
        violations = []

        # 1. 标普 500 白名单校验
        if proposal.get("ticker") not in sp500_whitelist:
            violations.append(f"标的 {proposal.get('ticker')} 不在 S&P 500 白名单中")

        # 2. 7 天二元财报事件避让
        if days_to_earnings <= self.rules.get("earnings_blackout_days", 7):
            violations.append(f"距离财报发布仅剩 {days_to_earnings} 天 (需规避 7 天内二元事件)")

        # 3. 资产类型特定风控底线
        if asset_type == "EQUITY":
            pos_pct = proposal.get("position_pct", 0.0)
            if pos_pct > self.rules.get("max_single_stock_pct", 0.048):
                violations.append(f"正股单仓比例 {pos_pct:.2%} 超过 {self.rules.get('max_single_stock_pct'):.2%} 上限")
            if proposal.get("leverage", 1.0) > self.rules.get("max_leverage", 1.0):
                violations.append("正股禁止使用大于 1.0x 融资杠杆")

        elif asset_type == "OPTION":
            dte = proposal.get("dte", 0)
            min_dte = self.rules.get("min_option_dte", 14)
            max_dte = self.rules.get("max_option_dte", 60)
            
            # 期权到期日约束 (14 <= DTE <= 60)
            if not (min_dte <= dte <= max_dte):
                violations.append(f"期权 DTE={dte} 天不在允许范围 [{min_dte}, {max_dte}] 天内，严禁交易短线末日期权")
            
            # 单笔权利金成本上限 (<= 2.0%)
            cost_pct = proposal.get("cost_pct", 0.0)
            if cost_pct > self.rules.get("max_option_cost_pct", 0.02):
                violations.append(f"期权单笔权利金占比 {cost_pct:.2%} 超过 2.0% 上限")

        # 5. 必备字段完整性校验 (自适应正股与期权资产类别)
        for field in self.rules.get("required_fields", []):
            if field == "suggested_shares":
                if asset_type == "EQUITY" and (field not in proposal or proposal[field] is None):
                    violations.append("正股提案缺少必要字段: suggested_shares")
                elif asset_type == "OPTION" and (proposal.get("suggested_contracts") is None and proposal.get("suggested_shares") is None):
                    violations.append("期权提案缺少必要字段: suggested_contracts")
            elif field == "ticker":
                if proposal.get("ticker") is None and proposal.get("underlying_ticker") is None:
                    violations.append("缺少必要字段: ticker")
            else:
                if field not in proposal or proposal[field] is None:
                    violations.append(f"缺少必要字段: {field}")

        return (len(violations) == 0, violations)