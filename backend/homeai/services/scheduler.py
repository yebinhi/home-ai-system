"""Single-process daily planning loop. For HA use durable job queue in future."""
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from ..config import get_settings
from ..db import claim_scheduler_day, release_scheduler_day
from ..agents.energy_agent import run_energy_planning

logger = logging.getLogger(__name__)

async def daily_scheduler_loop():
    cfg = get_settings()
    while True:
        now = datetime.now(ZoneInfo(cfg.app_timezone))
        local_day = now.strftime("%Y-%m-%d")
        if now.hour >= cfg.plan_hour_local:
            if claim_scheduler_day(local_day, now.isoformat()):
                try:
                    await run_energy_planning()
                    logger.info("Finished daily 48-hour optimisation for %s", local_day)
                except Exception:
                    # Allow another automatic attempt in a subsequent poll.
                    logger.exception("Energy planning error; keeping existing schedule untouched")
                    release_scheduler_day(local_day)
        await asyncio.sleep(60)
