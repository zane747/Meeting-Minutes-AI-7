"""管理中心路由（等級 1 超級管理員專屬）。"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.database_models import Meeting

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
    """管理中心：顯示所有會議紀錄（含上傳者資訊）。"""
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.creator))
        .order_by(Meeting.created_at.desc())
    )
    meetings = list(result.scalars().all())

    response = templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={"meetings": meetings, "current_user": current_user},
    )
    response.headers["Cache-Control"] = "no-store"
    return response
