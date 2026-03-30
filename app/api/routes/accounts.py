"""帳號管理路由：帳號列表、修改密碼、停用/啟用、刪除、角色變更。

權限規則：
- 帳號列表：等級 1 看全部、等級 2 只看等級 3、等級 3 禁止訪問
- 停用/啟用/刪除：等級 1 可操作等級 2+3、等級 2 只能操作等級 3
- 角色變更：僅等級 1
- 修改密碼：所有已登入使用者（修改自己的）
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounts"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# === 帳號列表（等級 1+2）===


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(2)),  # 等級 1 和 2 可訪問
) -> HTMLResponse:
    """帳號管理頁面：根據角色過濾帳號列表。"""
    all_users = await auth_service.get_all_users(db)

    # 根據操作者角色過濾顯示的帳號
    if current_user["role"] == 1:
        # 等級 1：看到全部
        users = all_users
    else:
        # 等級 2：只看到等級 3
        users = [u for u in all_users if u.role == 3]

    response = templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={"users": users, "current_user": current_user},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


# === 修改密碼（所有已登入使用者）===


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


# === 停用/啟用 API（等級 1+2）===


@router.post("/api/accounts/{user_id}/toggle-active")
async def toggle_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(2)),
):
    """切換帳號啟用/停用狀態。等級 2 只能操作等級 3。"""
    success, message = await auth_service.toggle_user_active(
        db, user_id, current_user["user_id"], current_user["role"]
    )
    if not success:
        raise HTTPException(status_code=403, detail=message)
    return {"detail": message}


# === 刪除帳號 API（等級 1+2）===


@router.delete("/api/accounts/{user_id}")
async def delete_account(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(2)),
):
    """刪除帳號。等級 2 只能刪除等級 3。"""
    success, message = await auth_service.delete_user(
        db, user_id, current_user["user_id"], current_user["role"]
    )
    if not success:
        raise HTTPException(status_code=403, detail=message)
    return {"detail": message}


# === 角色變更 API（僅等級 1）===


class ChangeRoleRequest(BaseModel):
    """角色變更請求。"""
    role: int


@router.post("/api/accounts/{user_id}/change-role")
async def change_role(
    user_id: str,
    data: ChangeRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(1)),  # 僅等級 1
):
    """變更帳號角色等級。"""
    success, message = await auth_service.change_role(
        db, user_id, data.role, current_user["user_id"]
    )
    if not success:
        raise HTTPException(status_code=403, detail=message)
    return {"detail": message}
