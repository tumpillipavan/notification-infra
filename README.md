# CYEPRO — AI-Native Notification Engine

> A production-grade notification decision engine that solves alert fatigue, message duplication, and time-sensitivity — with full explainability, user authentication, and a live dashboard UI.

---

## 🚀 Keys Feature

- **Authentication System**: Secure signup/login with session cookies, password toggle, balloon animation on signup, and user avatar on dashboard.
- **Decision Pipeline**: 7-stage evaluation per event — Expiry → Dedupe → Near-Dedupe → Critical Priority → Fatigue → AI Score → Rule Engine.
- **Explainability Layer**: Every decision returns a full "Decision Trace" showing exactly why a notification was sent, deferred (`LATER`), or suppressed (`NEVER`).
- **AI-Native Deduplication**: Simulated semantic similarity to block near-duplicate spam (ready for FAISS/LLM upgrade).
- **Intelligent Fatigue Control**: Max 5 notifications/hr per user, 2-min cooldown, with critical priority override.
- **Hot-Swappable Rules**: Versioned business rules updated live via API — no redeployment needed.
- **Observability**: Real-time metrics on latency, dedupe rates, and decision breakdown.
- **Zero-SQL**: Fully in-memory — no database dependencies, instant startup.

---

## 🏗 Architecture

See [architecture.md](architecture.md) for a full component breakdown.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI (Python) |
| Server | Uvicorn (ASGI) |
| Validation | Pydantic |
| Auth | Session cookies (SHA-256 hashed passwords) |
| Storage | In-memory (Zero-SQL) |
| AI Scoring | Simulated (keyword-based, ready for LLM) |
| Deployment | Render (render.yaml included) |

---

## 🚦 Getting Started (Local)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the engine
python -m app.main

# 3. Open in browser
# http://localhost:8000
```

You'll be redirected to `/login`. Sign up first at `/signup`, then log in to access the dashboard.

---

## 📄 Pages

| Route | Description |
|---|---|
| `/` | Dashboard (protected — requires login) |
| `/login` | Login page with password toggle |
| `/signup` | Signup with balloon celebration & auto-login |
| `/docs` | Interactive Swagger API console |
| `/audit` | Live notification decision log |
| `/metrics` | System performance stats |
| `/logout` | Clears session and redirects to login |

---

## 📡 API Endpoints

### Auth
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/signup` | Register + auto-login (session cookie set) |
| `POST` | `/api/login` | Login (session cookie set) |
| `GET` | `/logout` | Clear session |

### Core Engine
| Method | Path | Description |
|---|---|---|
| `POST` | `/notify` | Submit a notification event for decision |
| `POST` | `/rules` | Create/update a triage rule |
| `GET` | `/metrics` | Engine performance stats |
| `GET` | `/audit` | Full notification decision log |

#### Example: Send a Notification
```json
POST /notify
{
  "user_id": "user_123",
  "event_type": "transaction",
  "message": "You received $100",
  "priority_hint": "low",
  "dedupe_key": "txn_abc_001"
}
```

#### Response includes Decision Trace:
```json
{
  "decision": "NOW",
  "reason": "Passed all checks",
  "trace": ["Expiry check passed", "Exact duplicate check passed", "AI Score: 0.63", "Rule engine check passed"],
  "latency_ms": 1.2,
  "fallback_triggered": false
}
```

---

## 🛡 Fallback Strategy

If AI scoring or the rule engine throws an exception, the system falls back to a safe heuristic:
- `critical` → Always `NOW`
- `promotion` → `LATER`
- All others → `NOW`

---

## ☁️ Deploying to Render

A `render.yaml` is included. Set these fields on Render:

| Field | Value |
|---|---|
| Root Directory | `notification_engine` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

> ⚠️ Free tier: data resets on restart (in-memory only). First wake-up may take ~30s.

---

## 📈 Future Scalability

- **Production Dedupe**: Replace token-overlap with FAISS or pgvector embedding search.
- **Persistent Storage**: Migrate from in-memory to PostgreSQL (Render add-on available).
- **Distributed Queue**: Celery + Redis/Kafka for deferred notifications at scale.
- **LLM Rule Engine**: Accept natural-language rules translated to JSON via Gemini.
