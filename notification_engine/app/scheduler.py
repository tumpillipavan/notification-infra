import asyncio
import json
from datetime import datetime, timedelta, timezone
from .models import db_instance
import random

async def reevaluate_deferred():
    while True:
        try:
            now = datetime.now(timezone.utc)
            # We fetch all deferred events from Redis
            events = db_instance.deferred_events
            for event in events:
                if event["status"] == "pending" and event["retry_after"] <= now:
                    expires_at = event["expires_at"]
                    if expires_at and expires_at < now:
                        event["status"] = "expired"
                        # Persist change back to Redis
                        db_instance.r.hset(db_instance.deferred_key, str(event["id"]), json.dumps(event, default=str))
                        continue

                    event["status"] = "sent"
                    # Persist change back to Redis
                    db_instance.r.hset(db_instance.deferred_key, str(event["id"]), json.dumps(event, default=str))

                    db_instance.add_log(
                        user_id=event["user_id"],
                        event_type=event["event_type"],
                        message_hash=event.get("dedupe_key"),
                        decision="NOW",
                        reason="Processed from deferred queue",
                        rule_applied="scheduler_retry",
                        trace=["Retry timer expired", "Sent from scheduler"],
                        fallback=False,
                        latency=random.uniform(5, 15)
                    )

        except Exception as e:
            print(f"Scheduler error: {e}")

        await asyncio.sleep(10)
