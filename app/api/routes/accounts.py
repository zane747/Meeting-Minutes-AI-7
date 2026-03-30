"""帳號管理路由：帳號列表、修改密碼、停用/啟用、刪除。

這個檔案的結構跟 auth.py 類似：
- 頁面路由（GET）→ 渲染 HTML 模板
- 表單處理（POST）→ 處理表單資料
- API 路由（POST/DELETE）→ 回傳 JSON（給前端 JavaScript 呼叫）
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# === 帳號列表 ===


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """帳號管理頁面：顯示所有帳號列表。"""
    users = await auth_service.get_all_users(db)
    response = templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={"users": users, "current_user": current_user},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# === 修改密碼 ===


@router.get("/accounts/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """顯示修改密碼頁面。"""
    response = templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context={"current_user": current_user},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/accounts/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> HTMLResponse:
    """處理修改密碼表單。"""
    success, message = await auth_service.change_password(
        db, current_user["user_id"], old_password, new_password
    )

    context = {"current_user": current_user}
    if success:
        context["message"] = message
    else:
        context["error"] = message

    response = templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context=context,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# === 停用/啟用 API ===


@router.post("/api/accounts/{user_id}/toggle-active")
async def toggle_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """切換帳號啟用/停用狀態（API，回傳 JSON）。"""
    success, message = await auth_service.toggle_user_active(
        db, user_id, current_user["user_id"]
    )
    if not success:
        raise HTTPException(status_code=403, detail=message)
    return {"detail": message}


# === 刪除帳號 API ===


@router.delete("/api/accounts/{user_id}")
async def delete_account(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """刪除帳號（API，回傳 JSON）。前端需先二次確認。"""
    success, message = await auth_service.delete_user(
        db, user_id, current_user["user_id"]
    )
    if not success:
        raise HTTPException(status_code=403, detail=message)
    return {"detail": message}
