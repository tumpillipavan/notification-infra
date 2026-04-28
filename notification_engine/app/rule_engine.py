from typing import List, Optional, Any

class RuleEngine:
    def evaluate_rules(self, event_type: str, rules: List[Any]) -> Optional[Any]:
        active_rules = []
        for r in rules:
            r_type = r.event_type if hasattr(r, 'event_type') else r.get('event_type')
            r_active = r.active_flag if hasattr(r, 'active_flag') else r.get('active_flag')
            if r_type == event_type and r_active:
                active_rules.append(r)

        if not active_rules:
            return None

        def get_version(r):
            return r.version if hasattr(r, 'version') else r.get('version', 1)

        active_rules.sort(key=get_version, reverse=True)
        return active_rules[0]

    def should_suppress(self, rule: Any, current_count: int) -> bool:
        if not rule:
            return False
        max_per_hour = rule.max_per_hour if hasattr(rule, 'max_per_hour') else rule.get('max_per_hour', 0)
        return current_count >= max_per_hour
