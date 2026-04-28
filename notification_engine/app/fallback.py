def heuristic_fallback(event_data: dict) -> dict:
    priority = event_data.get("priority", "low").lower()
    event_type = event_data.get("event_type", "default").lower()

    if priority == "critical":
        return {
            "decision": "NOW",
            "reason": "Fallback: Critical events are sent NOW by default.",
            "rule_applied": "fallback_critical_v1"
        }

    if event_type == "promotion":
        return {
            "decision": "LATER",
            "reason": "Fallback: Promotions are deferred during system issues.",
            "rule_applied": "fallback_promo_v1"
        }

    return {
        "decision": "NOW",
        "reason": "Fallback: Defaulting to send for standard events.",
        "rule_applied": "fallback_default_v1"
    }
