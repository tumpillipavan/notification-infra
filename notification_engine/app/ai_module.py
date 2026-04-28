import random

def score_event(event_data: dict) -> float:
    priority = event_data.get("priority", "low").lower()

    if priority == "critical":
        return random.uniform(0.85, 1.0)

    message = event_data.get("message", "").lower()
    if any(word in message for word in ["urgent", "security", "fail", "alert"]):
        return random.uniform(0.7, 0.9)

    if any(word in message for word in ["promo", "deal", "discount", "offer"]):
        return random.uniform(0.1, 0.4)

    return random.uniform(0.4, 0.7)
