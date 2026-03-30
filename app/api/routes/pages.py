"""HTML 頁面路由。

【新手導讀】這個檔案定義所有「頁面」的路由（使用者在瀏覽器看到的頁面）。
每個路由函式都加上了 Depends(get_current_user)，表示必須登入才能訪問。
如果未登入，get_current_user 會自動把使用者導向 /login。

current_user 參數不只是用來「擋人」，還會被傳入模板的 context，
讓 base.html 的導覽列知道要顯示使用者名稱和登出按鈕。
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.database_models import Meeting, User

router = APIRouter(tags=["pages"])


def _no_cache_response(template_response: HTMLResponse) -> HTMLResponse:
    """為受保護頁面加上 Cache-Control: no-store header。

    【新手導讀】這行 header 告訴瀏覽器「不要快取這個頁面」。
    如果沒有這個設定，使用者登出後按「上一頁」，
    瀏覽器可能會顯示快取的頁面內容（即使 session 已清除）。
    對應 FR-014 和 SC-004。
    """
    template_response.headers["Cache-Control"] = "no-store"
    return template_response

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """首頁（上傳頁面，含 Provider 選擇）。

    需要登入才能訪問。current_user 由 get_current_user 依賴注入。
    """
    return _no_cache_response(templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "default_mode": settings.MODEL_MODE,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "current_user": current_user,
        },
    ))


@router.get("/meetings", response_class=HTMLResponse)
async def history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """歷史紀錄頁（依時間倒序）。根據角色和可見性過濾。"""
    from sqlalchemy import or_

    user_role = current_user.get("role", 3)
    user_id = current_user["user_id"]

    query = select(Meeting)

    if user_role == 1:
        # 等級 1（超級管理員）：看全部（含所有人的 private，用於除錯）
        pass
    elif user_role == 2:
        # 等級 2（管理員）：自己的全部 + 公開的 + 同級管理員的同級可見
        creator_alias = User
        query = query.outerjoin(creator_alias, Meeting.created_by == creator_alias.id).where(
            or_(
                Meeting.created_by == user_id,  # 自己的（含 private）
                Meeting.visibility == "public",  # 公開的
                Meeting.created_by.is_(None),  # 既有資料（無上傳者）
                (Meeting.visibility == "same_level") & (creator_alias.role == 2),  # 同級管理員的同級可見
            )
        )
    else:
        # 等級 3（一般使用者）：自己的全部 + 公開的 + 同級一般使用者的同級可見
        creator_alias = User
        query = query.outerjoin(creator_alias, Meeting.created_by == creator_alias.id).where(
            or_(
                Meeting.created_by == user_id,  # 自己的（含 private）
                Meeting.visibility == "public",  # 公開的
                Meeting.created_by.is_(None),  # 既有資料
                (Meeting.visibility == "same_level") & (creator_alias.role == 3),  # 同級一般使用者的同級可見
            )
        )

    result = await db.execute(
        query.options(selectinload(Meeting.creator))
        .order_by(Meeting.created_at.desc())
    )
    meetings = list(result.scalars().all())

    return _no_cache_response(templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"meetings": meetings, "current_user": current_user},
    ))


@router.get("/meetings/{meeting_id}", response_class=HTMLResponse)
async def meeting_detail(
    meeting_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """結果頁（逐字稿 + 摘要 + Action Items）。需要登入。"""
    result = await db.execute(
        select(Meeting)
        .options(
            selectinload(Meeting.action_items),
            selectinload(Meeting.annotation_files),
            selectinload(Meeting.creator),
        )
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        return _no_cache_response(templates.TemplateResponse(
            request=request,
            name="meeting.html",
            context={"meeting": None, "error": "會議紀錄不存在", "current_user": current_user},
        ))

    is_owner = meeting.created_by == current_user["user_id"]
    is_superadmin = current_user.get("role", 3) == 1

    # 可見性檢查：private 和 same_level 都要擋
    if not is_owner and not is_superadmin:
        if meeting.visibility == "private":
            return _no_cache_response(templates.TemplateResponse(
                request=request,
                name="meeting.html",
                context={"meeting": None, "error": "此為私人會議紀錄，無權檢視", "current_user": current_user},
            ))
        if meeting.visibility == "same_level":
            creator_role = meeting.creator.role if meeting.creator else None
            if creator_role != current_user.get("role", 3):
                return _no_cache_response(templates.TemplateResponse(
                    request=request,
                    name="meeting.html",
                    context={"meeting": None, "error": "此會議紀錄僅同等級可檢視", "current_user": current_user},
                ))

    # 編輯權限：必須先有檢視權限，再看 allow_edit
    can_edit = is_owner or is_superadmin or meeting.allow_edit

    return _no_cache_response(templates.TemplateResponse(
        request=request,
        name="meeting.html",
        context={
            "meeting": meeting,
            "ollama_enabled": settings.OLLAMA_ENABLED,
            "current_user": current_user,
            "is_owner": is_owner,
            "can_edit": can_edit,
        },
    ))
