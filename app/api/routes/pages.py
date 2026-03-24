"""HTML 頁面路由。"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.database_models import Meeting

router = APIRouter(tags=["pages"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """首頁（上傳頁面，含 Provider 選擇）。"""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "default_mode": settings.MODEL_MODE,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
        },
    )


@router.get("/meetings", response_class=HTMLResponse)
async def history(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """歷史紀錄頁（依時間倒序）。"""
    result = await db.execute(
        select(Meeting).order_by(Meeting.created_at.desc())
    )
    meetings = list(result.scalars().all())

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"meetings": meetings},
    )


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(
    meeting_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """結果頁（逐字稿 + 摘要 + Action Items）。"""
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.action_items),
            selectinload(Meeting.annotation_files),
        )
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        return templates.TemplateResponse(
            request=request,
            name="meeting.html",
            context={"meeting": None, "error": "會議紀錄不存在"},
        )

    return templates.TemplateResponse(
        request=request,
        name="meeting.html",
        context={
            "meeting": meeting,
            "ollama_enabled": settings.OLLAMA_ENABLED,
        },
    )
