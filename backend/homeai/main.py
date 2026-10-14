"""Home AI FastAPI backend. Loopback-only host publishing in compose."""
import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .db import initialize, latest_plan, recent_events, recent_plans, save_event
from .models import ChatInput, ChatOutput
from .integrations.foxess import FoxCloud
from .services.energy_service import schedule_preview
from .agents.energy_agent import run_energy_planning
from .services.scheduler import daily_scheduler_loop
from .agents.security_agent import record_protect_alarm
from .agents.home import answer

logger = logging.getLogger("homeai")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize()
    cfg = get_settings()
    task = asyncio.create_task(daily_scheduler_loop()) if cfg.run_scheduler else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

app = FastAPI(title="Home AI System", version="1.0.0", lifespan=lifespan)
cfg = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in cfg.allowed_origins.split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-HomeAI-Token"],
)

@app.get("/api/health")
async def health():
    return {"ok": True, "mode": "DEMO" if get_settings().mock_mode else "LIVE_READ_ONLY", "device_writes": False,
            "time": datetime.now(timezone.utc).isoformat()}

@app.get("/api/energy/status")
async def energy_status():
    try:
        return (await FoxCloud().status()).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get("/api/energy/generation")
async def energy_generation():
    try:
        return (await FoxCloud().generation()).model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get("/api/energy/raw")
async def raw_telemetry():
    try:
        return await FoxCloud().raw_variables()
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc

@app.get("/api/energy/plan")
async def energy_plan():
    plan = latest_plan()
    return plan.model_dump(mode="json") if plan else {"message": "No plan yet"}

@app.post("/api/energy/plan")
async def generate_plan():
    try:
        return (await run_energy_planning()).model_dump(mode="json")
    except Exception as exc:
        logger.exception("Plan generation failed")
        raise HTTPException(503, str(exc)) from exc

@app.get("/api/energy/history")
async def energy_history(limit: int = Query(20, ge=1, le=50)):
    return [{
        "id": p.id, "created_at": p.created_at.isoformat(),
        "source": p.source, "net_cost_gbp": p.predicted_net_cost_gbp,
        "horizon_hours": p.horizon_hours, "executable": p.executable,
    } for p in recent_plans(limit)]

@app.get("/api/system/config")
async def system_config():
    cfg = get_settings()
    return {
        "mode": "DEMO" if cfg.mock_mode else "LIVE_READ_ONLY",
        "export_enabled": cfg.export_enabled,
        "vision_enabled": cfg.vision_enabled,
        "device_writes_enabled": False,
        "planning_hour_local": cfg.plan_hour_local,
        "timezone": cfg.app_timezone,
        "pv_kwp": cfg.pv_kwp,
        "battery_capacity_kwh": cfg.battery_capacity_kwh,
    }

@app.get("/api/energy/schedule-preview")
async def energy_schedule_preview():
    plan = latest_plan()
    if not plan:
        raise HTTPException(404, "No plan")
    return schedule_preview(plan)

@app.get("/api/security/events")
async def get_events(limit: int = Query(30, ge=1, le=100)):
    return [e.model_dump(mode="json") for e in recent_events(limit)]

async def _authenticate_webhook(token: str | None):
    settings = get_settings()
    if not token or not hmac.compare_digest(token, settings.protect_webhook_token):
        raise HTTPException(401, "Invalid webhook token")
    if not settings.mock_mode and settings.protect_webhook_token == "change-me-before-live":
        raise HTTPException(503, "Replace default webhook token")

@app.api_route("/api/webhooks/unifi", methods=["GET", "POST"])
async def unifi_webhook(request: Request, x_homeai_token: str | None = Header(None)):
    await _authenticate_webhook(x_homeai_token)
    if request.method == "POST":
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, "Expected UniFi JSON event") from exc
    else:
        payload = {"timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                   "event_id": request.query_params.get("id") or request.query_params.get("eventId"),
                   "alarm": {"name": request.query_params.get("alarm", "Protect GET Alarm"), "triggers": []}}
    event, inserted = record_protect_alarm(payload)
    # Security baseline independent of vision/LLM. Extend with optional event queue,
    # event snapshot retrieval, vision analysis, notifications after device integration.
    return {"accepted": True, "new": inserted, "event_id": event.id}

@app.post("/api/chat", response_model=ChatOutput)
async def chat(inp: ChatInput):
    try:
        return ChatOutput(answer=await answer(inp.message))
    except Exception as exc:
        logger.warning("Chat unavailable: %s", exc)
        raise HTTPException(503, "Conversational agent unavailable. Check MCP servers and OpenAI settings.") from exc
