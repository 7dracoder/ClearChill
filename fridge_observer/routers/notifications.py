"""Notifications REST API router."""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from fridge_observer.db import get_db
from fridge_observer.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/activity-log")
async def get_activity_log(limit: int = 100):
    """Get the activity log entries, most recent first."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, item_id, item_name, action, source, occurred_at
               FROM activity_log
               ORDER BY occurred_at DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows]


@router.get("/weekly-report")
async def get_weekly_report():
    """Get the weekly waste report: expired vs consumed counts."""
    # Calculate the start of the current week (Monday)
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_start_str = week_start.strftime("%Y-%m-%d %H:%M:%S")

    async with get_db() as db:
        # Count expired items this week
        cursor = await db.execute(
            """SELECT COUNT(*) FROM activity_log
               WHERE action = 'expired' AND occurred_at >= ?""",
            (week_start_str,),
        )
        row = await cursor.fetchone()
        expired_count = row[0] if row else 0

        # Count consumed items this week (removed)
        cursor = await db.execute(
            """SELECT COUNT(*) FROM activity_log
               WHERE action = 'removed' AND occurred_at >= ?""",
            (week_start_str,),
        )
        row = await cursor.fetchone()
        consumed_count = row[0] if row else 0

        # Previous week for comparison
        prev_week_start = week_start - timedelta(weeks=1)
        prev_week_start_str = prev_week_start.strftime("%Y-%m-%d %H:%M:%S")

        cursor = await db.execute(
            """SELECT COUNT(*) FROM activity_log
               WHERE action = 'expired' AND occurred_at >= ? AND occurred_at < ?""",
            (prev_week_start_str, week_start_str),
        )
        row = await cursor.fetchone()
        prev_expired_count = row[0] if row else 0

        cursor = await db.execute(
            """SELECT COUNT(*) FROM activity_log
               WHERE action = 'removed' AND occurred_at >= ? AND occurred_at < ?""",
            (prev_week_start_str, week_start_str),
        )
        row = await cursor.fetchone()
        prev_consumed_count = row[0] if row else 0

    return {
        "week_start": week_start_str,
        "expired_count": expired_count,
        "consumed_count": consumed_count,
        "prev_week_expired_count": prev_expired_count,
        "prev_week_consumed_count": prev_consumed_count,
    }


@router.get("/streak")
async def get_streak():
    """Get the zero-waste streak (consecutive weeks with no expired items)."""
    settings = get_settings()

    if not settings.gamification_enabled:
        return {"streak": 0, "gamification_enabled": False}

    now = datetime.now(timezone.utc)
    streak = 0
    week_offset = 0

    while True:
        # Calculate week boundaries
        week_end = now - timedelta(weeks=week_offset)
        week_end = (week_end - timedelta(days=week_end.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_start = week_end - timedelta(weeks=1)

        week_start_str = week_start.strftime("%Y-%m-%d %H:%M:%S")
        week_end_str = week_end.strftime("%Y-%m-%d %H:%M:%S")

        async with get_db() as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM activity_log
                   WHERE action = 'expired' AND occurred_at >= ? AND occurred_at < ?""",
                (week_start_str, week_end_str),
            )
            row = await cursor.fetchone()
            expired_this_week = row[0] if row else 0

        if expired_this_week > 0:
            break

        # Check if there was any activity this week (to avoid counting empty weeks)
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT COUNT(*) FROM activity_log
                   WHERE occurred_at >= ? AND occurred_at < ?""",
                (week_start_str, week_end_str),
            )
            row = await cursor.fetchone()
            activity_count = row[0] if row else 0

        if activity_count == 0 and week_offset > 0:
            # No activity in this past week, stop counting
            break

        streak += 1
        week_offset += 1

        # Safety limit
        if week_offset > 52:
            break

    return {
        "streak": streak,
        "gamification_enabled": True,
        "message": f"🌿 {streak} week{'s' if streak != 1 else ''} zero-waste streak!" if streak > 0 else "Start your zero-waste streak this week!",
    }
