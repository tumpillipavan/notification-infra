from .models import db_instance
from .decision_engine import DecisionEngine
from .dedupe_service import DedupeService
from .fatigue_controller import FatigueController
from .rule_engine import RuleEngine
from typing import Dict, Any

# Global instances for the worker process
rule_engine = RuleEngine()
dedupe_service = DedupeService()
fatigue_controller = FatigueController()
decision_engine = DecisionEngine(dedupe_service, fatigue_controller, rule_engine)

def process_notification_task(data: Dict[str, Any]):
    user_id = data.get("user_id")
    event_data = data 
    
    # Fetch active rules
    active_rules = [r for r in db_instance.rules if r["active_flag"]]
    
    # Process through Decision Engine
    # DecisionEngine already handles logging via db_instance.add_log
    result = decision_engine.decide(
        user_id, 
        event_data, 
        active_rules, 
        history=db_instance.notification_logs
    )
    # Log to Redis so it appears in the Dashboard and Metrics
    db_instance.add_log(
        user_id=user_id,
        event_type=event_data.get("event_type", "unknown"),
        message_hash=str(hash(event_data.get("message", ""))),
        decision=result.get("decision", "ERROR"),
        reason=result.get("reason", "Unknown"),
        rule_applied=result.get("rule_applied", "none"),
        trace=result.get("trace", []),
        fallback=result.get("fallback_triggered", False),
        latency=result.get("latency_ms", 0.0)
    )
    
    # Handle Deferment
    if result["decision"] == "LATER":
        db_instance.add_deferred(
            user_id=user_id,
            event_type=event_data.get("event_type"),
            message=event_data.get("message"),
            dedupe_key=event_data.get("dedupe_key"),
            priority_hint=event_data.get("priority_hint"),
            expires_at=event_data.get("expires_at")
        )
    
    return result
