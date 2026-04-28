from datetime import datetime, timedelta, timezone
from typing import Dict, List
from .models import db_instance

class FatigueController:
    def __init__(self, max_per_hour: int = 5, cooldown_minutes: int = 2):
        self.max_per_hour = max_per_hour
        self.cooldown_minutes = cooldown_minutes

    def check_fatigue(self, user_id: str) -> tuple[bool, str]:
        user_history = db_instance.get_fatigue_history(user_id)

        if len(user_history) >= self.max_per_hour:
            return False, f"User exceeded hourly limit of {self.max_per_hour}"

        if user_history:
            last_sent = user_history[-1]
            if datetime.now(timezone.utc) < last_sent + timedelta(minutes=self.cooldown_minutes):
                return False, f"Cooldown active. Wait {self.cooldown_minutes} minutes between push alerts."

        return True, ""

    def record_sent(self, user_id: str):
        db_instance.record_fatigue_event(user_id)
