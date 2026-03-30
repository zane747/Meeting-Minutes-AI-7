"""管理中心路由（等級 1 超級管理員專屬）。"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.database_models import Meeting, MeetingStatus, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(1)),  # 僅等級 1
) -> HTMLResponse:
    """管理中心：系統總覽儀表板。"""
    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)

    # 統計數據（並行查詢）
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )).scalar() or 0
    total_meetings = (await db.execute(select(func.count(Meeting.id)))).scalar() or 0
    today_meetings = (await db.execute(
        select(func.count(Meeting.id)).where(Meeting.created_at >= today_start)
    )).scalar() or 0
    completed_meetings = (await db.execute(
        select(func.count(Meeting.id)).where(Meeting.status == MeetingStatus.COMPLETED)
    )).scalar() or 0
    failed_meetings = (await db.execute(
        select(func.count(Meeting.id)).where(Meeting.status == MeetingStatus.FAILED)
    )).scalar() or 0

    stats = {
        "total_users": total_users,
        "active_users": active_users,
        "total_meetings": total_meetings,
        "today_meetings": today_meetings,
        "completed_meetings": completed_meetings,
        "failed_meetings": failed_meetings,
    }

    response = templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={"stats": stats, "current_user": current_user},
    )
    response.headers["Cache-Control"] = "no-store"
    return response
