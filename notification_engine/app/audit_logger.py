import logging
from datetime import datetime, timezone
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AuditLogger")

class AuditLogger:
    @staticmethod
    def log_decision(user_id: str, event_data: dict, decision_info: dict):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "event_type": event_data.get("event_type"),
            "priority_hint": event_data.get("priority_hint"),
            "decision": decision_info.get("decision"),
            "reason": decision_info.get("reason"),
            "rule_applied": decision_info.get("rule_applied"),
            "trace": decision_info.get("trace"),
            "fallback_triggered": decision_info.get("fallback_triggered", False),
            "latency_ms": decision_info.get("latency_ms")
        }
        logger.info(f"AUDIT_LOG: {json.dumps(log_entry)}")
