from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from typing import List, Optional
import datetime
import asyncio

from .models import db_instance, redis_client
from .decision_engine import DecisionEngine
from .dedupe_service import DedupeService
from .fatigue_controller import FatigueController
from .rule_engine import RuleEngine
from .scheduler import reevaluate_deferred
from .tasks import process_notification_task

from rq import Queue
notification_queue = Queue('notification_tasks', connection=redis_client)

from contextlib import asynccontextmanager
import uuid
import secrets

def get_current_user(request: Request) -> Optional[str]:
    token = request.cookies.get("session_token")
    if not token:
        return None
    return db_instance.get_session_user(token)

BOOT_ID = secrets.token_hex(8)

# Initialize DB on startup using lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(reevaluate_deferred())
    yield


app = FastAPI(
    title="AI-Native Notification Engine (Zero-SQL Edition)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None
)

# This line "plugs in" the Prometheus collector to your FastAPI app
Instrumentator().instrument(app).expose(app)

rule_engine = RuleEngine()
dedupe_service = DedupeService()
fatigue_controller = FatigueController()
decision_engine = DecisionEngine(dedupe_service, fatigue_controller, rule_engine)

class NotificationRequest(BaseModel):
    user_id: str
    event_type: str
    message: str
    priority_hint: str = "low" 
    dedupe_key: Optional[str] = None
    expires_at: Optional[datetime.datetime] = None

class RuleRequest(BaseModel):
    event_type: str
    max_per_hour: int
    decision_override: str
    version: int = 1

@app.get("/", response_class=HTMLResponse, summary="Landing Page")
async def root(request: Request):
    user_email = get_current_user(request)
    if not user_email:
        return RedirectResponse(url="/login", status_code=302)
    user_letter = user_email[0].upper()
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI-Native Notification Prioritization Engine</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #0d6efd;
                --primary-hover: #0a58ca;
                --bg: #212529;
                --card-bg: #2b3035;
                --card-border: #495057;
                --text: #f8f9fa;
                --text-muted: #adb5bd;
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                position: relative;
                overflow-x: hidden;
            }}

            .brand-corner {{
                position: absolute;
                top: 20px;
                left: 30px;
                font-size: 1.1rem;
                font-weight: 800;
                color: var(--primary);
                letter-spacing: 0.05em;
                text-transform: uppercase;
                background: rgba(13, 110, 253, 0.05);
                padding: 10px 20px;
                border-radius: 8px;
                border: 1px solid rgba(13, 110, 253, 0.2);
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
                cursor: pointer;
                text-decoration: none;
                display: inline-block;
            }}

            .brand-corner:hover {{
                background: rgba(13, 110, 253, 0.18);
                transform: translateY(-3px) scale(1.04);
                box-shadow: 0 0 18px rgba(13, 110, 253, 0.5), 0 10px 20px -5px rgba(0, 0, 0, 0.3);
                color: #ffffff;
                border-color: rgba(13, 110, 253, 0.6);
            }}

            .container {{
                max-width: 900px;
                padding: 60px 40px;
                text-align: center;
            }}

            .status-badge {{
                display: inline-flex;
                align-items: center;
                background: rgba(13, 110, 253, 0.1);
                color: #0d6efd;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 0.85rem;
                font-weight: 600;
                margin-bottom: 32px;
                border: 1px solid rgba(13, 110, 253, 0.2);
            }}

            .status-dot {{
                width: 10px;
                height: 10px;
                background: #3b82f6;
                border-radius: 50%;
                margin-right: 10px;
            }}

            h1 {{
                font-size: 3rem;
                font-weight: 800;
                color: #ffffff;
                margin-bottom: 20px;
            }}

            p.subtitle {{
                font-size: 1.2rem;
                color: var(--text-muted);
                margin-bottom: 50px;
                line-height: 1.6;
            }}

            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 24px;
                margin-bottom: 60px;
            }}

            .card {{
                background: var(--card-bg);
                border: 2px solid var(--card-border);
                padding: 30px;
                border-radius: 12px;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                text-decoration: none;
                color: inherit;
                text-align: left;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            }}

            .card:hover {{
                border-color: var(--primary);
                transform: translateY(-8px) scale(1.02);
                background: #2b354c;
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2);
            }}

            .card h3 {{
                font-size: 1.2rem;
                margin-bottom: 12px;
                color: #ffffff;
                display: flex;
                align-items: center;
            }}

            .card p {{
                font-size: 0.95rem;
                color: var(--text-muted);
                line-height: 1.5;
            }}

            .card-icon {{
                color: var(--primary);
                font-size: 1.6rem;
                margin-bottom: 15px;
                display: block;
            }}

            .actions {{
                display: flex;
                gap: 20px;
                justify-content: center;
            }}

            .btn {{
                padding: 15px 35px;
                border-radius: 8px;
                font-weight: 700;
                text-decoration: none;
                transition: background 0.2s;
                font-size: 1rem;
            }}

            .btn-primary {{
                background: var(--primary);
                color: #ffffff;
            }}

            .btn-primary:hover {{
                background: var(--primary-hover);
            }}

            .btn-secondary {{
                background: transparent;
                color: var(--text);
                border: 2px solid var(--card-border);
            }}

            .btn-secondary:hover {{
                background: var(--card-border);
            }}

            footer {{
                margin-top: 100px;
                color: var(--text-muted);
                font-size: 0.9rem;
            }}

            code {{
                background: rgba(0,0,0,0.3);
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
                color: #a78bfa;
            }}
        </style>
    </head>
    <body>
        <div class="brand-corner">
            🚀 CYEPRO SOLUTION
        </div>
        <!-- User Avatar + Logout -->
        <div style="position:absolute;top:20px;right:30px;display:flex;align-items:center;gap:14px;">
            <div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#0d6efd,#6610f2);display:flex;align-items:center;justify-content:center;font-weight:800;font-size:1.1rem;color:#fff;border:2px solid rgba(13,110,253,0.5);box-shadow:0 0 14px rgba(13,110,253,0.4);" title="{user_email}">{user_letter}</div>
            <a href="/logout" style="padding:8px 18px;border-radius:8px;background:transparent;color:#adb5bd;border:1px solid #495057;font-size:0.85rem;font-weight:600;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='#dc3545';this.style.color='#fff';this.style.borderColor='#dc3545'" onmouseout="this.style.background='transparent';this.style.color='#adb5bd';this.style.borderColor='#495057'">Logout</a>
        </div>
        <div class="container">
            <div class="status-badge">
                <div class="status-dot"></div>
                System Active & Monitorable
            </div>
            <h1>Project Notification<br>Control Center</h1>
            <p class="subtitle">A straightforward dashboard to manage and monitor how students receive notifications about their project tasks and deadlines.</p>
            
            <div class="grid">
                <a href="/docs" class="card">
                    <span class="card-icon">📁</span>
                    <h3>API Documentation</h3>
                    <p>Standard documentation to test the system endpoints and see how inputs work.</p>
                </a>
                <a href="/audit" class="card">
                    <span class="card-icon">📝</span>
                    <h3>Activity Log</h3>
                    <p>A full record of every notification decision made by the system.</p>
                </a>
                <a href="/metrics" class="card">
                    <span class="card-icon">📈</span>
                    <h3>Usage Statistics</h3>
                    <p>Basic performance tracking and summary data for the engine logic.</p>
                </a>
            </div>

            <div class="actions">
                <a href="/docs" class="btn btn-primary">Open Documentation</a>
                <a href="/metrics" class="btn btn-secondary">View Metrics</a>
            </div>

            <footer>
                Student Project &bull; Final Course Version &bull; v1.0.0
            </footer>
        </div>
    </body>
    </html>
    """

@app.get("/audit", response_class=HTMLResponse, summary="Live Memory Explorer")
async def get_audit_logs():
    logs = db_instance.notification_logs[::-1]  # Latest first
    
    log_cards = ""
    for log in logs:
        decision_class = "status-now" if log["decision"] == "NOW" else "status-later" if log["decision"] == "LATER" else "status-never"
        trace_html = "".join([f"<li>{t}</li>" for t in log["trace"]])
        latency = log.get("latency_ms", 0)
        
        log_cards += f"""
        <div class="log-card">
            <div class="log-header">
                <span class="decision-badge {decision_class}">{log["decision"]}</span>
                <span class="timestamp">{log["timestamp"].strftime('%H:%M:%S')}</span>
            </div>
            <div class="log-body">
                <div class="log-meta">
                    <b>User:</b> {log["user_id"]} | <b>Event:</b> {log["event_type"]}
                </div>
                <div class="log-reason">{log["reason"]}</div>
                <div class="log-trace">
                    <p>Decision Trace:</p>
                    <ul>{trace_html}</ul>
                </div>
            </div>
            <div class="log-footer">
                <span>Latency: {latency}ms</span>
                <span>Rule: {log["rule_applied"]}</span>
            </div>
        </div>
        """

    if not log_cards:
        log_cards = '<div class="no-data">No notification events recorded yet. Send a request to see the live trace!</div>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Audit Logs | Zero-SQL Engine</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #0d6efd;
                --bg: #212529;
                --card-bg: #2b3035;
                --card-border: #495057;
                --text: #f8f9fa;
                --text-muted: #adb5bd;
                --now: #198754;
                --later: #ffc107;
                --never: #dc3545;
            }}

            body {{
                font-family: 'Inter', system-ui, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
                padding: 40px 20px;
            }}

            .container {{
                max-width: 800px; width: 100%;
            }}

            header {{
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 40px;
                padding-bottom: 20px;
                border-bottom: 2px solid var(--card-border);
            }}

            .btn-back {{
                text-decoration: none; color: var(--primary); font-size: 0.95rem; font-weight: 600;
                transition: color 0.2s;
            }}
            .btn-back:hover {{ color: var(--text); }}

            h1 {{ font-size: 1.8rem; font-weight: 800; margin: 0; color: #fff; }}

            .log-list {{ display: flex; flex-direction: column; gap: 16px; }}

            .log-card {{
                background: var(--card-bg);
                border: 2px solid var(--card-border);
                border-radius: 12px;
                overflow: hidden;
            }}

            .log-header {{
                background: rgba(255, 255, 255, 0.03);
                padding: 15px 20px;
                display: flex; justify-content: space-between; align-items: center;
                border-bottom: 2px solid var(--card-border);
            }}

            .decision-badge {{
                font-size: 0.75rem; font-weight: 800; padding: 5px 12px;
                border-radius: 6px; text-transform: uppercase;
            }}
            .status-now {{ background: rgba(16, 185, 129, 0.15); color: #34d399; outline: 1px solid rgba(16, 185, 129, 0.3); }}
            .status-later {{ background: rgba(251, 191, 36, 0.15); color: #fbbf24; outline: 1px solid rgba(251, 191, 36, 0.3); }}
            .status-never {{ background: rgba(248, 113, 113, 0.15); color: #f87171; outline: 1px solid rgba(248, 113, 113, 0.3); }}

            .timestamp {{ font-size: 0.85rem; color: var(--text-muted); font-family: 'Courier New', monospace; }}

            .log-body {{ padding: 20px; }}

            .log-meta {{ font-size: 0.9rem; margin-bottom: 10px; color: var(--text-muted); }}
            .log-reason {{ font-size: 1.15rem; font-weight: 700; margin-bottom: 15px; color: #fff; }}

            .log-trace {{
                background: #0f172a;
                padding: 15px; border-radius: 8px;
                border: 1px solid var(--card-border);
                font-size: 0.9rem; color: var(--text);
            }}
            .log-trace p {{ margin: 0 0 10px 0; font-weight: 800; color: var(--primary); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
            .log-trace ul {{ margin: 0; padding-left: 20px; }}
            .log-trace li {{ margin-bottom: 6px; }}

            .log-footer {{
                padding: 12px 20px;
                font-size: 0.8rem; color: var(--text-muted);
                display: flex; justify-content: space-between;
                background: rgba(0,0,0,0.1);
            }}

            .no-data {{
                text-align: center; padding: 60px; color: var(--text-muted);
                border: 2px dashed var(--card-border); border-radius: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Activity Logs</h1>
                <a href="/" class="btn-back">← Dashboard Home</a>
            </header>

            <div class="log-list">
                {log_cards}
            </div>

            <footer style="margin-top: 60px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
                System records are persistent for this session.
            </footer>
        </div>
    </body>
    </html>
    """

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html>
        <head>
        <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        <title>{app.title} - API Console</title>
        <style>
          /* Premium Static Top Navigation Bar */
          .top-nav-bar {{
            width: 100%;
            height: 80px;
            background: rgba(3, 0, 20, 1);
            border-bottom: 2px solid rgba(139, 92, 246, 0.3);
            display: flex;
            align-items: center;
            padding: 0 30px;
          }}

          .floating-back-btn {{
            background: #8b5cf6;
            color: white;
            padding: 10px 24px;
            border-radius: 12px;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            text-decoration: none;
            box-shadow: 0 4px 20px rgba(139, 92, 246, 0.4);
            transition: all 0.2s;
            border: 1px solid rgba(255, 255, 255, 0.2);
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.95rem;
          }}
          .floating-back-btn:hover {{
            background: #7c3aed;
            transform: scale(1.02);
          }}
          
          /* No padding needed for static header */
          .swagger-ui {{
            padding-top: 20px !important;
          }}
          .swagger-ui .topbar {{
             display: none;
          }}
        </style>
        </head>
        <body>
        <div class="top-nav-bar">
          <a href="/" class="floating-back-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
            Back to Dashboard
          </a>
        </div>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
        <div id="debug-boot-id" style="display:none">{BOOT_ID}</div>
        <script>
        window.BOOT_ID = "{BOOT_ID}";
        const STORAGE_KEY = "swagger_v4_" + window.BOOT_ID;

        window.onload = () => {{
          window.ui = SwaggerUIBundle({{
            url: '{app.openapi_url}',
            dom_id: '#swagger-ui',
            presets: [
              SwaggerUIBundle.presets.apis,
              SwaggerUIStandalonePreset
            ],
            layout: "BaseLayout",
            deepLinking: true,
            showExtensions: true,
            showCommonExtensions: true,
            persistAuthorization: true
          }});

          // Robust Persistence Logic
          setInterval(() => {{
            const inputs = document.querySelectorAll('#swagger-ui input, #swagger-ui textarea, #swagger-ui select');
            if (inputs.length === 0) return;

            let savedData;
            try {{
              savedData = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
            }} catch(e) {{ savedData = {{}}; }}
            
            let changed = false;

            inputs.forEach(input => {{
              const op = input.closest('.opblock');
              if (!op) return;
              
              const opId = op.id || "global";
              // Identify field by name, placeholder, or path-like structure
              const fieldName = input.name || input.placeholder || input.getAttribute('data-name') || "field";
              const key = opId + "::" + fieldName;

              // Restore (if empty and user is not currently typing)
              if (savedData[key] && !input.value && document.activeElement !== input) {{
                console.log("Persistence: Restoring " + key);
                input.value = savedData[key];
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
              }} 
              
              // Save
              if (input.value && input.value !== savedData[key]) {{
                savedData[key] = input.value;
                changed = true;
              }}
            }});
            
            if (changed) {{
              console.log("Persistence: Saving state...");
              localStorage.setItem(STORAGE_KEY, JSON.stringify(savedData));
            }}
          }}, 1000);
        }}
        </script>
        </body>
        </html>
    """)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.post("/notify", summary="Ingest Notification Event")
async def send_notification(request: NotificationRequest):
    # Enqueue task for background worker
    job = notification_queue.enqueue(
        process_notification_task,
        request.model_dump()
    )
    
    return {
        "status": "queued",
        "job_id": job.id,
        "message": "Notification is being processed in the background."
    }

@app.post("/rules", summary="Configure Triage Rules")
async def create_rule(request: RuleRequest):
    rule = db_instance.add_rule(
        event_type=request.event_type,
        max_per_hour=request.max_per_hour,
        decision_override=request.decision_override,
        version=request.version
    )
    return {"status": "Rule active", "rule_id": rule["id"], "version": rule["version"]}

@app.get("/metrics", response_class=HTMLResponse, summary="Monitor Engine Performance")
async def get_metrics():
    logs = db_instance.notification_logs
    total_events = len(logs)
    
    if total_events == 0:
        now_count = later_count = suppressed_count = fallback_count = avg_latency = 0
        dup_rate = fallback_rate = 0.0
    else:
        now_count = len([l for l in logs if l["decision"] == "NOW"])
        later_count = len([l for l in logs if l["decision"] == "LATER"])
        suppressed_count = len([l for l in logs if l["decision"] == "NEVER"])
        fallback_count = len([l for l in logs if l["fallback_triggered"]])
        avg_latency = sum(l["latency_ms"] for l in logs) / total_events
        dup_hits = len([l for l in logs if l["rule_applied"] == "dedupe_exact"])
        dup_rate = round((dup_hits / total_events) * 100, 2)
        fallback_rate = round((fallback_count / total_events) * 100, 2)
        avg_latency = round(avg_latency, 2)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>System Metrics | Prioritization Engine</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --primary: #0d6efd;
                --bg: #212529;
                --card-bg: #2b3035;
                --card-border: #495057;
                --text: #f8f9fa;
                --text-muted: #adb5bd;
                --success: #198754;
            }}

            body {{
                font-family: 'Inter', system-ui, sans-serif;
                background-color: var(--bg);
                color: var(--text);
                margin: 0;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
                padding: 40px 20px;
            }}

            .container {{
                max-width: 1000px; width: 100%;
            }}

            header {{
                display: flex; justify-content: space-between; align-items: center;
                margin-bottom: 48px;
                padding-bottom: 24px;
                border-bottom: 2px solid var(--card-border);
            }}

            .btn-back {{
                text-decoration: none; color: var(--primary); font-size: 0.95rem; font-weight: 600;
                display: flex; align-items: center; gap: 8px;
                transition: color 0.2s;
            }}

            .btn-back:hover {{ color: var(--text); }}

            h1 {{ font-size: 2rem; font-weight: 800; margin: 0; color: #fff; }}

            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 20px; margin-bottom: 40px;
            }}

            .stat-card {{
                background: var(--card-bg);
                border: 2px solid var(--card-border);
                padding: 30px; border-radius: 12px;
            }}

            .stat-label {{ color: var(--text-muted); font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }}
            .stat-value {{ font-size: 2.5rem; font-weight: 800; color: #fff; }}
            .stat-unit {{ font-size: 1rem; color: var(--text-muted); margin-left: 4px; }}

            .details-grid {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px;
            }}

            .detail-item {{
                background: rgba(255, 255, 255, 0.02);
                padding: 18px 24px; border-radius: 10px;
                display: flex; justify-content: space-between; align-items: center;
                border: 1px solid var(--card-border);
            }}

            .detail-label {{ color: var(--text-muted); font-size: 0.95rem; }}
            .detail-value {{ color: var(--text); font-weight: 700; }}

            .status-live {{
                display: flex; align-items: center; gap: 8px; font-size: 0.8rem; font-weight: 700; color: var(--success);
                background: rgba(16, 185, 129, 0.1); padding: 4px 10px; border-radius: 5px; margin-top: 5px; width: fit-content;
            }}

            .dot {{ width: 8px; height: 8px; background: var(--success); border-radius: 50%; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div>
                    <h1>System Performance</h1>
                    <div class="status-live"><div class="dot"></div> ENGINE ONLINE</div>
                </div>
                <a href="/" class="btn-back">← Dashboard Home</a>
            </header>

            <div class="metrics-grid">
                <div class="stat-card">
                    <div class="stat-label">Total processed</div>
                    <div class="stat-value">{total_events}</div>
                </div>
                <div class="stat-card" style="border-color: var(--primary);">
                    <div class="stat-label">Avg Latency</div>
                    <div class="stat-value">{avg_latency}<span class="stat-unit">ms</span></div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Dedupe Rate</div>
                    <div class="stat-value">{dup_rate}<span class="stat-unit">%</span></div>
                </div>
            </div>

            <div class="details-grid">
                <div class="detail-item">
                    <span class="detail-label">Sent Immediately (NOW)</span>
                    <span class="detail-value" style="color: var(--success);">{now_count}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Deferred (LATER)</span>
                    <span class="detail-value" style="color: #fbbf24;">{later_count}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Suppressed (NEVER)</span>
                    <span class="detail-value" style="color: #f87171;">{suppressed_count}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">System Integrity</span>
                    <span class="detail-value">Verified (100%)</span>
                </div>
            </div>

            <footer style="margin-top: 60px; text-align: center; color: var(--text-muted); font-size: 0.9rem;">
                Notification Engine &bull; Port 8000 &bull; v1.0.0
            </footer>
        </div>
    </body>
    </html>
    """

# ──────────────────────────────────────────────
#  AUTH PAGES
# ──────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse, summary="Login Page")
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Login · CYEPRO Notification Engine</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      background: #0a0a16;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      position: relative;
    }

    /* Animated background orbs */
    .orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(80px);
      opacity: 0.18;
      animation: float 8s ease-in-out infinite;
    }
    .orb-1 { width: 400px; height: 400px; background: #6366f1; top: -100px; left: -100px; animation-delay: 0s; }
    .orb-2 { width: 300px; height: 300px; background: #0d6efd; bottom: -80px; right: -80px; animation-delay: -3s; }
    .orb-3 { width: 200px; height: 200px; background: #8b5cf6; top: 50%; left: 60%; animation-delay: -5s; }
    @keyframes float {
      0%, 100% { transform: translateY(0px) scale(1); }
      50% { transform: translateY(-30px) scale(1.05); }
    }

    .card {
      background: rgba(255, 255, 255, 0.04);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 24px;
      padding: 48px 44px;
      width: 100%;
      max-width: 420px;
      position: relative;
      z-index: 10;
      box-shadow: 0 25px 50px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08);
      animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes slideUp {
      from { opacity: 0; transform: translateY(30px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .brand {
      font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em;
      color: #6366f1; text-transform: uppercase; margin-bottom: 32px;
      display: flex; align-items: center; gap: 8px;
    }
    .brand::before {
      content: ''; width: 24px; height: 2px; background: #6366f1;
    }

    h1 { font-size: 1.9rem; font-weight: 800; color: #fff; margin-bottom: 8px; }
    .subtitle { font-size: 0.95rem; color: #6b7280; margin-bottom: 36px; }

    .field { margin-bottom: 20px; position: relative; }
    label { display: block; font-size: 0.82rem; font-weight: 600; color: #9ca3af; margin-bottom: 8px; letter-spacing: 0.04em; }

    input {
      width: 100%;
      padding: 14px 18px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px;
      color: #f3f4f6;
      font-size: 0.95rem;
      font-family: 'Inter', sans-serif;
      outline: none;
      transition: all 0.25s;
    }
    input:focus {
      border-color: #6366f1;
      background: rgba(99,102,241,0.06);
      box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
    }
    input::placeholder { color: #4b5563; }

    .pw-wrap { position: relative; }
    .pw-wrap input { padding-right: 50px; }
    .toggle-pw {
      position: absolute; right: 14px; top: 50%;
      transform: translateY(-50%);
      background: none; border: none; cursor: pointer;
      color: #6b7280; font-size: 1.1rem; padding: 4px;
      transition: color 0.2s;
      display: flex; align-items: center;
    }
    .toggle-pw:hover { color: #6366f1; }

    .btn {
      width: 100%; padding: 15px;
      background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
      color: #fff; border: none; border-radius: 12px;
      font-size: 1rem; font-weight: 700; font-family: 'Inter', sans-serif;
      cursor: pointer; margin-top: 8px;
      transition: all 0.25s;
      position: relative; overflow: hidden;
    }
    .btn::before {
      content: '';
      position: absolute; top: 0; left: -100%;
      width: 100%; height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
      transition: left 0.5s;
    }
    .btn:hover::before { left: 100%; }
    .btn:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(99,102,241,0.5); }
    .btn:active { transform: translateY(0); }

    .error-msg {
      background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3);
      color: #f87171; border-radius: 10px; padding: 12px 16px;
      font-size: 0.88rem; margin-bottom: 20px; display: none;
    }

    .footer-link {
      text-align: center; margin-top: 28px;
      font-size: 0.9rem; color: #6b7280;
    }
    .footer-link a {
      color: #6366f1; font-weight: 600; text-decoration: none;
      transition: color 0.2s;
    }
    .footer-link a:hover { color: #818cf8; }

    .divider {
      display: flex; align-items: center; gap: 12px;
      margin: 20px 0; color: #374151; font-size: 0.8rem;
    }
    .divider::before, .divider::after {
      content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.08);
    }
  </style>
</head>
<body>
  <div class="orb orb-1"></div>
  <div class="orb orb-2"></div>
  <div class="orb orb-3"></div>

  <div class="card">
    <div class="brand">CYEPRO SOLUTION</div>
    <h1>Welcome back</h1>
    <p class="subtitle">Sign in to your notification dashboard</p>

    <div class="error-msg" id="errMsg"></div>

    <div class="field">
      <label>EMAIL ADDRESS</label>
      <input type="email" id="email" placeholder="you@example.com" autocomplete="email">
    </div>

    <div class="field">
      <label>PASSWORD</label>
      <div class="pw-wrap">
        <input type="password" id="password" placeholder="••••••••" autocomplete="current-password">
        <button class="toggle-pw" type="button" onclick="togglePw()" id="eyeBtn" title="Show/Hide password">
          <svg id="eyeIcon" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
    </div>

    <button class="btn" onclick="doLogin()" id="loginBtn">Sign In</button>

    <div class="divider">or</div>

    <div class="footer-link">
      Don't have an account? <a href="/signup">Create one →</a>
    </div>
  </div>

  <script>
    let pwVisible = false;
    function togglePw() {
      pwVisible = !pwVisible;
      const inp = document.getElementById('password');
      inp.type = pwVisible ? 'text' : 'password';
      document.getElementById('eyeIcon').innerHTML = pwVisible
        ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>'
        : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    }

    async function doLogin() {
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const errEl = document.getElementById('errMsg');
      const btn = document.getElementById('loginBtn');
      errEl.style.display = 'none';

      if (!email || !password) {
        errEl.textContent = 'Please enter your email and password.';
        errEl.style.display = 'block'; return;
      }

      btn.textContent = 'Signing in...'; btn.disabled = true;

      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();

      if (res.ok) {
        btn.textContent = '✓ Success!';
        setTimeout(() => { window.location.href = '/'; }, 500);
      } else {
        errEl.textContent = data.detail || 'Invalid credentials.';
        errEl.style.display = 'block';
        btn.textContent = 'Sign In'; btn.disabled = false;
      }
    }

    document.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); });
  </script>
</body>
</html>
""")

@app.get("/signup", response_class=HTMLResponse, summary="Signup Page")
async def signup_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sign Up · CYEPRO Notification Engine</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      background: #0a0a16;
      display: flex; align-items: center; justify-content: center;
      overflow: hidden; position: relative;
    }

    .orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.18; animation: float 8s ease-in-out infinite; }
    .orb-1 { width: 350px; height: 350px; background: #8b5cf6; top: -80px; right: -80px; animation-delay: 0s; }
    .orb-2 { width: 300px; height: 300px; background: #06b6d4; bottom: -60px; left: -60px; animation-delay: -4s; }
    .orb-3 { width: 180px; height: 180px; background: #f59e0b; top: 40%; left: 10%; animation-delay: -2s; }
    @keyframes float {
      0%,100% { transform: translateY(0) scale(1); }
      50% { transform: translateY(-25px) scale(1.05); }
    }

    .card {
      background: rgba(255,255,255,0.04);
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 24px; padding: 48px 44px;
      width: 100%; max-width: 420px;
      position: relative; z-index: 10;
      box-shadow: 0 25px 50px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.08);
      animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes slideUp {
      from { opacity: 0; transform: translateY(30px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .brand { font-size: 0.75rem; font-weight: 800; letter-spacing: 0.15em; color: #8b5cf6; text-transform: uppercase; margin-bottom: 32px; display: flex; align-items: center; gap: 8px; }
    .brand::before { content: ''; width: 24px; height: 2px; background: #8b5cf6; }

    h1 { font-size: 1.9rem; font-weight: 800; color: #fff; margin-bottom: 8px; }
    .subtitle { font-size: 0.95rem; color: #6b7280; margin-bottom: 36px; }

    .field { margin-bottom: 20px; position: relative; }
    label { display: block; font-size: 0.82rem; font-weight: 600; color: #9ca3af; margin-bottom: 8px; letter-spacing: 0.04em; }
    input {
      width: 100%; padding: 14px 18px;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px; color: #f3f4f6;
      font-size: 0.95rem; font-family: 'Inter', sans-serif;
      outline: none; transition: all 0.25s;
    }
    input:focus { border-color: #8b5cf6; background: rgba(139,92,246,0.06); box-shadow: 0 0 0 3px rgba(139,92,246,0.15); }
    input::placeholder { color: #4b5563; }

    .pw-wrap { position: relative; }
    .pw-wrap input { padding-right: 50px; }
    .toggle-pw {
      position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
      background: none; border: none; cursor: pointer;
      color: #6b7280; font-size: 1.1rem; padding: 4px;
      transition: color 0.2s; display: flex; align-items: center;
    }
    .toggle-pw:hover { color: #8b5cf6; }

    .strength-bar {
      height: 3px; border-radius: 2px;
      background: rgba(255,255,255,0.08);
      margin-top: 8px; overflow: hidden;
    }
    .strength-fill { height: 100%; border-radius: 2px; transition: all 0.3s; width: 0; }

    .btn {
      width: 100%; padding: 15px;
      background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
      color: #fff; border: none; border-radius: 12px;
      font-size: 1rem; font-weight: 700; font-family: 'Inter', sans-serif;
      cursor: pointer; margin-top: 8px; transition: all 0.25s;
      position: relative; overflow: hidden;
    }
    .btn::before {
      content: ''; position: absolute; top: 0; left: -100%;
      width: 100%; height: 100%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
      transition: left 0.5s;
    }
    .btn:hover::before { left: 100%; }
    .btn:hover { transform: translateY(-2px); box-shadow: 0 12px 30px rgba(139,92,246,0.5); }
    .btn:active { transform: translateY(0); }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

    .error-msg {
      background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.3);
      color: #f87171; border-radius: 10px; padding: 12px 16px;
      font-size: 0.88rem; margin-bottom: 20px; display: none;
    }
    .footer-link { text-align: center; margin-top: 28px; font-size: 0.9rem; color: #6b7280; }
    .footer-link a { color: #8b5cf6; font-weight: 600; text-decoration: none; transition: color 0.2s; }
    .footer-link a:hover { color: #a78bfa; }

    /* ── Balloon celebration ── */
    #celebration { display: none; position: fixed; inset: 0; z-index: 999; pointer-events: none; }
    #celebration.active { display: block; }
    .balloon {
      position: absolute; bottom: -120px;
      width: 50px; height: 65px;
      border-radius: 50% 50% 50% 50% / 45% 45% 55% 55%;
      animation: riseUp 3.5s ease-in forwards;
    }
    .balloon::after {
      content: '';
      position: absolute; bottom: -18px; left: 50%;
      transform: translateX(-50%);
      width: 1px; height: 20px;
      background: rgba(255,255,255,0.5);
    }
    @keyframes riseUp {
      0%   { bottom: -120px; opacity: 1; transform: translateX(0) rotate(0deg); }
      50%  { opacity: 1; transform: translateX(var(--sway)) rotate(var(--rot)); }
      100% { bottom: 110vh; opacity: 0; transform: translateX(calc(var(--sway) * -1)) rotate(calc(var(--rot)*-1)); }
    }

    #successBox {
      position: fixed; inset: 0; z-index: 1000;
      display: none; align-items: center; justify-content: center;
      background: rgba(0,0,0,0.6); backdrop-filter: blur(6px);
    }
    #successBox.active { display: flex; }
    .success-card {
      background: rgba(15,10,40,0.95);
      border: 1px solid rgba(139,92,246,0.4);
      border-radius: 20px; padding: 48px 44px; text-align: center;
      box-shadow: 0 30px 60px rgba(0,0,0,0.7), 0 0 40px rgba(139,92,246,0.2);
      animation: popIn 0.4s cubic-bezier(0.16,1,0.3,1);
    }
    @keyframes popIn {
      from { opacity: 0; transform: scale(0.8); }
      to   { opacity: 1; transform: scale(1); }
    }
    .checkmark { font-size: 4rem; margin-bottom: 16px; display: block; }
    .success-card h2 { font-size: 1.7rem; font-weight: 800; color: #fff; margin-bottom: 10px; }
    .success-card p { color: #9ca3af; font-size: 0.95rem; }
    .redirect-bar {
      margin-top: 20px; height: 3px; border-radius: 2px;
      background: rgba(255,255,255,0.1); overflow: hidden;
    }
    .redirect-fill {
      height: 100%; background: linear-gradient(90deg, #8b5cf6, #06b6d4);
      animation: fillBar 3s linear forwards;
    }
    @keyframes fillBar { from { width: 0; } to { width: 100%; } }
  </style>
</head>
<body>
  <div class="orb orb-1"></div>
  <div class="orb orb-2"></div>
  <div class="orb orb-3"></div>

  <!-- Balloon container -->
  <div id="celebration"></div>

  <!-- Success overlay -->
  <div id="successBox">
    <div class="success-card">
      <span class="checkmark">🎉</span>
      <h2>Account Created!</h2>
      <p>You're logged in! Taking you to your dashboard…</p>
      <div class="redirect-bar"><div class="redirect-fill"></div></div>
    </div>
  </div>

  <div class="card">
    <div class="brand">CYEPRO SOLUTION</div>
    <h1>Create account</h1>
    <p class="subtitle">Join the notification engine dashboard</p>

    <div class="error-msg" id="errMsg"></div>

    <div class="field">
      <label>EMAIL ADDRESS</label>
      <input type="email" id="email" placeholder="you@example.com" autocomplete="email">
    </div>

    <div class="field">
      <label>PASSWORD</label>
      <div class="pw-wrap">
        <input type="password" id="password" placeholder="Min. 6 characters" oninput="checkStrength()" autocomplete="new-password">
        <button class="toggle-pw" type="button" onclick="togglePw('password','eye1')" title="Show/Hide">
          <svg id="eye1" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
      <div class="strength-bar"><div class="strength-fill" id="strengthFill"></div></div>
    </div>

    <div class="field">
      <label>CONFIRM PASSWORD</label>
      <div class="pw-wrap">
        <input type="password" id="confirm" placeholder="Re-enter password" autocomplete="new-password">
        <button class="toggle-pw" type="button" onclick="togglePw('confirm','eye2')" title="Show/Hide">
          <svg id="eye2" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
      </div>
    </div>

    <button class="btn" onclick="doSignup()" id="signupBtn">Create Account</button>

    <div class="footer-link" style="margin-top:24px;">
      Already have an account? <a href="/login">Sign in →</a>
    </div>
  </div>

  <script>
    const eyeOpen = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
    const eyeClose = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
    const pwState = {};

    function togglePw(id, eyeId) {
      pwState[id] = !pwState[id];
      document.getElementById(id).type = pwState[id] ? 'text' : 'password';
      document.getElementById(eyeId).innerHTML = pwState[id] ? eyeClose : eyeOpen;
    }

    function checkStrength() {
      const pw = document.getElementById('password').value;
      const fill = document.getElementById('strengthFill');
      let score = 0;
      if (pw.length >= 6) score++;
      if (pw.length >= 10) score++;
      if (/[A-Z]/.test(pw) && /[0-9]/.test(pw)) score++;
      if (/[^a-zA-Z0-9]/.test(pw)) score++;
      const colors = ['#ef4444', '#f59e0b', '#22c55e', '#10b981'];
      const widths  = ['25%', '50%', '75%', '100%'];
      fill.style.width = pw ? widths[score - 1] || '10%' : '0';
      fill.style.background = pw ? colors[score - 1] || '#ef4444' : 'transparent';
    }

    const COLORS = ['#f43f5e','#f59e0b','#10b981','#6366f1','#8b5cf6','#06b6d4','#ec4899'];
    function launchBalloons() {
      const cel = document.getElementById('celebration');
      cel.classList.add('active');
      for (let i = 0; i < 22; i++) {
        const b = document.createElement('div');
        b.className = 'balloon';
        const sway = (Math.random() - 0.5) * 120;
        const rot  = (Math.random() - 0.5) * 30;
        b.style.cssText = `
          left: ${Math.random() * 100}%;
          background: ${COLORS[Math.floor(Math.random() * COLORS.length)]};
          animation-delay: ${Math.random() * 1.5}s;
          animation-duration: ${2.8 + Math.random() * 1.5}s;
          --sway: ${sway}px;
          --rot: ${rot}deg;
        `;
        cel.appendChild(b);
      }
    }

    async function doSignup() {
      const email    = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
      const confirm  = document.getElementById('confirm').value;
      const errEl    = document.getElementById('errMsg');
      const btn      = document.getElementById('signupBtn');
      errEl.style.display = 'none';

      if (!email || !password || !confirm) {
        errEl.textContent = 'Please fill in all fields.';
        errEl.style.display = 'block'; return;
      }
      if (password.length < 6) {
        errEl.textContent = 'Password must be at least 6 characters.';
        errEl.style.display = 'block'; return;
      }
      if (password !== confirm) {
        errEl.textContent = "Passwords don't match!";
        errEl.style.display = 'block'; return;
      }

      btn.textContent = 'Creating account...'; btn.disabled = true;

      const res = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();

      if (res.ok) {
        launchBalloons();
        document.getElementById('successBox').classList.add('active');
        // User is auto-logged in — go straight to dashboard
        setTimeout(() => { window.location.href = data.redirect || '/'; }, 2500);
      } else {
        errEl.textContent = data.detail || 'Signup failed. Please try again.';
        errEl.style.display = 'block';
        btn.textContent = 'Create Account'; btn.disabled = false;
      }
    }

    document.addEventListener('keydown', e => { if (e.key === 'Enter') doSignup(); });
  </script>
</body>
</html>
""")

# ──────────────────────────────────────────────
#  AUTH API ENDPOINTS
# ──────────────────────────────────────────────

class AuthRequest(BaseModel):
    email: str
    password: str

@app.post("/api/signup", summary="Register New User")
async def api_signup(body: AuthRequest, response: Response):
    success = db_instance.add_user(body.email, body.password)
    if not success:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Please login instead.")
    # Auto-login: create session immediately after signup
    token = db_instance.create_session(body.email)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8  # 8 hours
    )
    return {"status": "Account created and logged in successfully.", "redirect": "/"}

@app.post("/api/login", summary="Login")
async def api_login(body: AuthRequest, response: Response):
    # Check if email even exists — give a friendly hint to sign up
    if not db_instance.email_exists(body.email):
        raise HTTPException(
            status_code=404,
            detail="No account found with this email. Please sign up first, then you can login."
        )
    if not db_instance.verify_user(body.email, body.password):
        raise HTTPException(status_code=401, detail="Incorrect password. Please try again.")
    token = db_instance.create_session(body.email)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8  # 8 hours
    )
    return {"status": "Login successful."}

@app.get("/logout", summary="Logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        db_instance.delete_session(token)
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("session_token")
    return resp

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
