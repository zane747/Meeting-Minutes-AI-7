"""公告訊息 REST API 路由。"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models.database_models import Announcement
from app.models.schemas import (
    AnnouncementCreate,
    AnnouncementListItem,
    AnnouncementResponse,
    AnnouncementUpdate,
    MessageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


# === 權限檢查 ===


def _check_announcement_owner(announcement: Announcement, current_user: dict) -> None:
    """檢查當前使用者是否為發布者或超級管理員。"""
    is_owner = announcement.created_by == current_user["user_id"]
    is_superadmin = current_user.get("role", 3) == 1
    if not is_owner and not is_superadmin:
        raise HTTPException(status_code=403, detail="僅發布者或超級管理員可執行此操作")


# === CRUD ===


@router.post("", response_model=AnnouncementResponse)
async def create_announcement(
    data: AnnouncementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(2)),  # Role 1, 2 可建立
) -> Announcement:
    """建立公告。僅 Role 1、Role 2 可使用。"""
    announcement = Announcement(
        title=data.title,
        content=data.content,
        created_by=current_user["user_id"],
    )
    db.add(announcement)
    await db.commit()
    await db.refresh(announcement)
    return announcement


@router.get("", response_model=list[AnnouncementListItem])
async def list_announcements(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[Announcement]:
    """取得公告列表（置頂優先，時間倒序）。"""
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.creator))
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Announcement:
    """取得公告詳情。"""
    result = await db.execute(
        select(Announcement)
        .options(selectinload(Announcement.creator))
        .where(Announcement.id == announcement_id)
    )
    announcement = result.scalar_one_or_none()
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")
    return announcement


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    data: AnnouncementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Announcement:
    """編輯公告。僅發布者或超級管理員可編輯。"""
    announcement = await db.get(Announcement, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")

    _check_announcement_owner(announcement, current_user)

    if data.title is not None:
        announcement.title = data.title
    if data.content is not None:
        announcement.content = data.content

    await db.commit()
    await db.refresh(announcement)
    return announcement


@router.delete("/{announcement_id}", response_model=MessageResponse)
async def delete_announcement(
    announcement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """刪除公告。僅發布者或超級管理員可刪除。"""
    announcement = await db.get(Announcement, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")

    _check_announcement_owner(announcement, current_user)

    await db.delete(announcement)
    await db.commit()
    return MessageResponse(detail="公告已刪除")


@router.put("/{announcement_id}/pin", response_model=MessageResponse)
async def toggle_pin(
    announcement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(1)),  # 僅 Role 1
) -> MessageResponse:
    """切換置頂狀態。僅超級管理員可操作。"""
    announcement = await db.get(Announcement, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="公告不存在")

    announcement.is_pinned = not announcement.is_pinned
    await db.commit()
    return MessageResponse(detail="已置頂" if announcement.is_pinned else "已取消置頂")
