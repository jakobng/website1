from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from src.config import AppConfig
from src.service import process_replies, run_discovery_and_email


def start_scheduler(config: AppConfig) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_discovery_and_email,
        "interval",
        hours=config.discovery_interval_hours,
        kwargs={"config": config},
    )
    scheduler.add_job(
        process_replies,
        "interval",
        minutes=config.reply_check_minutes,
        kwargs={"config": config},
    )
    scheduler.start()
    return scheduler
