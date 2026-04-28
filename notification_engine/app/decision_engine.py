import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from .dedupe_service import DedupeService
from .fatigue_controller import FatigueController
from .ai_module import score_event
from .rule_engine import RuleEngine
from .fallback import heuristic_fallback
from .audit_logger import AuditLogger

class DecisionEngine:
    def __init__(self, dedupe_service: DedupeService, fatigue_controller: FatigueController, rule_engine: RuleEngine):
        self.dedupe = dedupe_service
        self.fatigue = fatigue_controller
        self.rules = rule_engine

    def decide(self, user_id: str, event_data: dict, active_rules: List[Any], history: List[dict] = []) -> dict:
        start_time = time.time()
        trace = []
        decision = "NOW"
        reason = "Passed all checks"
        rule_applied = "default_allow"
        fallback_triggered = False

        try:
            expires_at = event_data.get("expires_at")
            if expires_at and expires_at < datetime.now(timezone.utc):
                    decision = "NEVER"
                    reason = "Event expired before evaluation"
                    trace.append(f"Expiry check failed: {expires_at}")
                    return self._finalize(user_id, event_data, decision, reason, "expiry_rule", trace, start_time)
            trace.append("Expiry check passed")

            dedupe_key = event_data.get("dedupe_key")
            if dedupe_key and self.dedupe.check_exact_duplicate(user_id, dedupe_key):
                decision = "NEVER"
                reason = "Exact duplicate detected (dedupe_key hit)"
                trace.append("Exact duplicate check hit")
                return self._finalize(user_id, event_data, decision, reason, "dedupe_exact", trace, start_time)
            trace.append("Exact duplicate check passed")

            trace.append("Near duplicate check passed (simulated)")

            priority_hint = event_data.get("priority_hint", "low").lower()
            is_critical = (priority_hint == "critical")
            if is_critical:
                trace.append("Critical priority detected: Bypassing fatigue limits")
            else:
                trace.append("Standard priority: Subject to fatigue limits")

            if not is_critical:
                allowed, fatigue_reason = self.fatigue.check_fatigue(user_id)
                if not allowed:
                    decision = "LATER"
                    reason = fatigue_reason
                    rule_applied = "fatigue_rule_v1"
                    trace.append(f"Alert fatigue check failed: {fatigue_reason}")
                    return self._finalize(user_id, event_data, decision, reason, rule_applied, trace, start_time)
            trace.append("Alert fatigue check passed")

            ai_score = score_event(event_data)
            trace.append(f"AI Score: {ai_score:.2f}")

            event_type = event_data.get("event_type", "default")
            matching_rule = self.rules.evaluate_rules(event_type, active_rules)
            if matching_rule:
                rule_id = matching_rule.id if hasattr(matching_rule, 'id') else matching_rule.get('id')
                rule_version = matching_rule.version if hasattr(matching_rule, 'version') else matching_rule.get('version')
                decision_override = matching_rule.decision_override if hasattr(matching_rule, 'decision_override') else matching_rule.get('decision_override')
                rule_limit = matching_rule.max_per_hour if hasattr(matching_rule, 'max_per_hour') else matching_rule.get('max_per_hour', 999)

                sent_in_last_hour = [
                    l for l in history
                    if l["user_id"] == user_id and l["event_type"] == event_type and l["decision"] == "NOW"
                ]

                if len(sent_in_last_hour) >= rule_limit:
                    decision = decision_override
                    reason = f"Frequency limit ({rule_limit}/hr) exceeded for {event_type}"
                    rule_applied = f"rule_{rule_id}_v{rule_version}"
                    trace.append(f"Suppression rule matched: {rule_applied} - {reason}")
                    return self._finalize(user_id, event_data, decision, reason, rule_applied, trace, start_time)

                if ai_score < 0.3 and decision_override == "LATER":
                    decision = "LATER"
                    reason = f"Suppressed by {event_type} rule due to low AI score"
                    rule_applied = f"rule_{rule_id}_v{rule_version}"
                    trace.append(f"Suppression rule matched: {rule_applied}")
                    return self._finalize(user_id, event_data, decision, reason, rule_applied, trace, start_time)

            trace.append("Rule engine check passed")

        except Exception as e:
            fallback_triggered = True
            fallback_result = heuristic_fallback(event_data)
            decision = fallback_result["decision"]
            reason = fallback_result["reason"]
            rule_applied = fallback_result["rule_applied"]
            trace.append(f"INTERNAL ERROR: {str(e)}")
            trace.append(f"Fallback triggered: {rule_applied}")

        return self._finalize(user_id, event_data, decision, reason, rule_applied, trace, start_time, fallback_triggered)

    def _finalize(self, user_id, event_data, decision, reason, rule_applied, trace, start_time, fallback=False):
        latency = (time.time() - start_time) * 1000
        result = {
            "decision": decision,
            "reason": reason,
            "rule_applied": rule_applied,
            "trace": trace,
            "fallback_triggered": fallback,
            "latency_ms": latency
        }

        if decision != "NEVER":
            self.dedupe.add_to_cache(user_id, event_data.get("message", ""), event_data.get("dedupe_key"))

        if decision == "NOW":
            self.fatigue.record_sent(user_id)

        AuditLogger.log_decision(user_id, event_data, result)
        return result
