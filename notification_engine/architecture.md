# Architecture Overview - Notification Prioritization Engine

## Components

### 1. API Layer (FastAPI)
The entry point for all notification requests and rule management.

### 2. Decision Engine
The brain of the system. It orchestrates the evaluation pipeline for every notification.
- **Traceability**: Every decision includes a "Decision Trace" explaining why a specific action was taken.

### 3. Rule Engine (Configurable)
Evaluates human-defined and system-defined suppression rules.
- **Versioning**: Rules support versioning and active flags, allowing updates without redeployment.

### 4. AI Scoring Module (Simulated)
Simulates an AI-driven importance score for notifications.
- **Future Integration**: Designed to be replaced with LLM embeddings (Gemini/OpenAI).

### 5. Deduplication Service
Handles both exact and near-duplicate messages.
- **Near-Dedupe**: Uses a 10-minute window and token overlap similarity logic.

### 6. Alert Fatigue Controller
Protects users from notification overload.
- **Limits**: Max 5 notifications per hour per user.
- **Cooldown**: 2-minute gap between push notifications.
- **Critical Override**: Important notifications bypass fatigue limits.

### 7. Audit Logger (Explainability Layer)
A first-class component that records every decision, rule match, and fallback event for auditing.

### 8. Fallback Manager
Provides heuristic reliability if the AI or database components fail.

### 9. Storage Layer
Uses a high-performance in-memory dictionary-based storage system for this demo to persist rules, logs, and deferred events without the overhead of external database dependencies.

## Decision Pipeline Order
1. **Expiry Check**: Is the event already stale?
2. **Exact Duplicate Check**: Has this exact key been sent recently?
3. **Near Duplicate Check**: Is this message semantically similar to recent ones?
4. **Critical Priority Check**: Should we bypass fatigue limits?
5. **Alert Fatigue Check**: Has the user hit their hourly/cooldown limits?
6. **Promotional Suppression Rule**: Do specific business rules apply?
7. **Default Action**: Send NOW or defer.
