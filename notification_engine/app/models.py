from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import json
import hashlib
import secrets
import os
import redis

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def _parse_iso(ts: str) -> datetime:
    if not ts: return None
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

class DB:
    def __init__(self):
        self.r = redis_client
        self._next_rule_id_key = "notification:next_rule_id"
        self._next_log_id_key = "notification:next_log_id"
        self._next_deferred_id_key = "notification:next_deferred_id"
        self.users_key = "notification:users"
        self.rules_key = "notification:rules"
        self.logs_key = "notification:logs"
        self.deferred_key = "notification:deferred"

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def add_user(self, email: str, password: str) -> bool:
        if self.r.hexists(self.users_key, email.lower()):
            return False
        self.r.hset(self.users_key, email.lower(), self._hash_password(password))
        return True

    def verify_user(self, email: str, password: str) -> bool:
        stored = self.r.hget(self.users_key, email.lower())
        if not stored:
            return False
        return stored == self._hash_password(password)

    def create_session(self, email: str) -> str:
        token = secrets.token_hex(32)
        # Store session with 8 hour TTL
        self.r.setex(f"session:{token}", 60 * 60 * 8, email.lower())
        return token

    def get_session_user(self, token: str) -> Optional[str]:
        return self.r.get(f"session:{token}")

    def email_exists(self, email: str) -> bool:
        return self.r.hexists(self.users_key, email.lower())

    def delete_session(self, token: str):
        self.r.delete(f"session:{token}")

    def add_rule(self, event_type: str, max_per_hour: int, decision_override: str, version: int = 1):
        # Fetch current rules to deactivate old ones
        current_rules = self.rules
        for rule in current_rules:
            if rule["event_type"] == event_type:
                rule["active_flag"] = False
                self.r.hset(self.rules_key, str(rule["id"]), json.dumps(rule))

        rule_id = self.r.incr(self._next_rule_id_key)
        rule = {
            "id": rule_id,
            "event_type": event_type,
            "max_per_hour": max_per_hour,
            "decision_override": decision_override,
            "version": version,
            "active_flag": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.r.hset(self.rules_key, str(rule_id), json.dumps(rule))
        return rule

    @property
    def rules(self) -> List[Dict[str, Any]]:
        raw_rules = self.r.hvals(self.rules_key)
        return [json.loads(r) for r in raw_rules]

    def add_log(self, user_id: str, event_type: str, message_hash: str, decision: str, reason: str, rule_applied: str, trace: List[str], fallback: bool, latency: float):
        log_id = self.r.incr(self._next_log_id_key)
        log = {
            "id": log_id,
            "user_id": user_id,
            "event_type": event_type,
            "message_hash": message_hash,
            "decision": decision,
            "reason": reason,
            "rule_applied": rule_applied,
            "trace": trace,
            "fallback_triggered": fallback,
            "latency_ms": latency,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.r.lpush(self.logs_key, json.dumps(log))
        self.r.ltrim(self.logs_key, 0, 99) # Keep last 100 logs
        return log

    @property
    def notification_logs(self) -> List[Dict[str, Any]]:
        raw_logs = self.r.lrange(self.logs_key, 0, -1)
        logs = []
        for rl in raw_logs:
            log = json.loads(rl)
            log["timestamp"] = _parse_iso(log["timestamp"])
            logs.append(log)
        return logs

    def add_deferred(self, user_id: str, event_type: str, message: str, dedupe_key: str, priority_hint: str, expires_at: Optional[datetime]):
        deferred_id = self.r.incr(self._next_deferred_id_key)
        deferred = {
            "id": deferred_id,
            "user_id": user_id,
            "event_type": event_type,
            "message": message,
            "dedupe_key": dedupe_key,
            "priority_hint": priority_hint,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "retry_after": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            "status": "pending"
        }
        self.r.hset(self.deferred_key, str(deferred_id), json.dumps(deferred))
        return deferred

    @property
    def deferred_events(self) -> List[Dict[str, Any]]:
        raw_deferred = self.r.hvals(self.deferred_key)
        events = []
        for rd in raw_deferred:
            event = json.loads(rd)
            if event["expires_at"]:
                event["expires_at"] = _parse_iso(event["expires_at"])
            event["retry_after"] = _parse_iso(event["retry_after"])
            events.append(event)
        return events

    # --- Shared Brain Synchronization Helpers ---

    def get_fatigue_history(self, user_id: str) -> List[datetime]:
        key = f"notification:fatigue:{user_id}"
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        # Cleanup old entries using ZREMRANGEBYSCORE
        self.r.zremrangebyscore(key, "-inf", cutoff.timestamp())
        # Fetch remaining entries
        timestamps = self.r.zrange(key, 0, -1)
        return [datetime.fromtimestamp(float(ts), tz=timezone.utc) for ts in timestamps]

    def record_fatigue_event(self, user_id: str):
        key = f"notification:fatigue:{user_id}"
        now = datetime.now(timezone.utc).timestamp()
        self.r.zadd(key, {str(now): now})
        self.r.expire(key, 3600) # Ensure key expires after 1 hour of inactivity

    def is_duplicate(self, user_id: str, dedupe_key: str) -> bool:
        return self.r.sismember(f"notification:dedupe:{user_id}", dedupe_key)

    def add_dedupe_key(self, user_id: str, dedupe_key: str, window_minutes: int):
        key = f"notification:dedupe:{user_id}"
        self.r.sadd(key, dedupe_key)
        self.r.expire(key, window_minutes * 60)

db_instance = DB()
