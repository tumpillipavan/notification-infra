import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def test_notify():
    print("\n--- Testing /notify Endpoint ---")
    payload = {
        "user_id": "user_123",
        "event_type": "transaction",
        "message": "You received $100",
        "priority_hint": "low"
    }
    response = requests.post(f"{BASE_URL}/notify", json=payload)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_duplicates():
    print("\n--- Testing Deduplication ---")
    payload = {
        "user_id": "user_123",
        "event_type": "alert",
        "message": "Duplicate Alert",
        "dedupe_key": "unique_key_456"
    }
    # First call
    requests.post(f"{BASE_URL}/notify", json=payload)
    # Second call (Duplicate)
    response = requests.post(f"{BASE_URL}/notify", json=payload)
    print(f"Duplicate Hit Decision: {response.json()['decision']}")
    print(f"Reason: {response.json()['reason']}")

def test_critical_override():
    print("\n--- Testing Critical Override (Fatigue Bypass) ---")
    # Trigger 5 notifications to hit fatigue
    for i in range(5):
        requests.post(f"{BASE_URL}/notify", json={
            "user_id": "user_fatigue", "event_type": "info", "message": f"Spam {i}"
        })
    
    # 6th call - Standard (Should be LATER)
    res1 = requests.post(f"{BASE_URL}/notify", json={
        "user_id": "user_fatigue", "event_type": "info", "message": "Standard"
    })
    print(f"Standard (6th) Decision: {res1.json()['decision']}")

    # 7th call - Critical (Should be NOW)
    res2 = requests.post(f"{BASE_URL}/notify", json={
        "user_id": "user_fatigue", "event_type": "info", "message": "CRITICAL ALERT", "priority_hint": "critical"
    })
    print(f"Critical (7th) Decision: {res2.json()['decision']} (Bypassed Fatigue: {'critical priority' in str(res2.json()['trace']).lower() or 'critical priority detected' in str(res2.json()['trace']).lower()})")

def test_expiry():
    print("\n--- Testing Expiry Handling ---")
    past_time = (datetime.now() - timedelta(hours=1)).isoformat()
    payload = {
        "user_id": "user_123",
        "event_type": "alert",
        "message": "Stale message",
        "expires_at": past_time
    }
    response = requests.post(f"{BASE_URL}/notify", json=payload)
    print(f"Stale Message Decision: {response.json()['decision']}")
    print(f"Reason: {response.json()['reason']}")

def test_rules():
    print("\n--- Testing Rule Creation ---")
    payload = {
        "event_type": "promotion",
        "max_per_hour": 1,
        "decision_override": "LATER",
        "version": 2
    }
    response = requests.post(f"{BASE_URL}/rules", json=payload)
    print(f"Rule Creation Status: {response.json()['status']}")

def test_metrics():
    print("\n--- Testing Metrics Endpoint ---")
    response = requests.get(f"{BASE_URL}/metrics")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    # Note: Ensure the server is running (python -m app.main) before running this
    try:
        test_notify()
        test_duplicates()
        test_critical_override()
        test_expiry()
        test_rules()
        test_metrics()
    except Exception as e:
        print(f"Error during testing: {e}. Is the server running?")
