import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from .models import db_instance

class DedupeService:
    def __init__(self, window_minutes: int = 10):
        self.window_minutes = window_minutes

    def _get_hash(self, text: str) -> str:
        return hashlib.md5(text.lower().strip().encode()).hexdigest()

    def check_exact_duplicate(self, user_id: str, dedupe_key: str) -> bool:
        return db_instance.is_duplicate(user_id, dedupe_key)

    def check_near_duplicate(self, user_id: str, message: str) -> Optional[float]:
        # Near duplicate logic placeholder - could be enhanced with Redis Sets
        return None

    def add_to_cache(self, user_id: str, message: str, dedupe_key: Optional[str] = None):
        msg_hash = dedupe_key if dedupe_key else self._get_hash(message)
        db_instance.add_dedupe_key(user_id, msg_hash, self.window_minutes)

    def semantic_similarity_simulated(self, msg1: str, msg2: str) -> float:
        tokens1 = set(msg1.lower().split())
        tokens2 = set(msg2.lower().split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / len(union)
