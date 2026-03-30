"""認證相關路由：註冊、登入、登出。

這個檔案定義了 5 個端點：
- GET  /register → 顯示註冊頁面
- POST /register → 處理註冊表單
- GET  /login    → 顯示登入頁面
- POST /login    → 處理登入表單
- POST /logout   → 登出

路由層只負責「接收請求 → 呼叫 auth_service 處理 → 回傳回應」。
為什麼不把所有邏輯都寫在這裡？因為分層架構——
如果以後要把 bcrypt 換成別的演算法，只改 auth_service.py 就好，這個檔案不用動。
"""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# 找到 templates 資料夾的路徑
# 為什麼要用 Path 而不是寫死字串？因為不同電腦的路徑不同，
# 用 __file__（這個檔案自己的位置）往上推算，在任何電腦上都能正確找到。
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# === 註冊 ===


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """顯示註冊頁面。已登入的話直接跳首頁。"""

    # 為什麼要檢查登入狀態？
    # 因為已經登入的人不需要再註冊，讓他停在註冊頁沒有意義。
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
    )


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),    # 從表單的 <input name="username"> 取值
    password: str = Form(...),    # 從表單的 <input name="password"> 取值
    db: AsyncSession = Depends(get_db),  # 資料庫連線（自動注入）
) -> HTMLResponse:
    """處理註冊表單。

    流程：驗證帳號密碼格式 → 檢查帳號是否重複 → 建立帳號 → 自動登入 → 導向首頁。
    任何步驟失敗就重新顯示註冊頁面並帶上錯誤訊息。
    """

    # --- 伺服器端驗證 ---
    # 為什麼前端（HTML）已經有驗證了，後端還要再驗一次？
    # 因為前端驗證可以被繞過！使用者可以用瀏覽器開發者工具改掉 HTML，
    # 或直接用工具（curl、Postman）發請求，完全跳過前端。
    # 所以後端驗證是「最後一道防線」，絕對不能省。

    if len(username) < 3 or len(username) > 30:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "帳號長度必須在 3~30 字元之間", "username_value": username},
        )

    # 為什麼限制只能英數字和底線？
    # 防止帳號裡有特殊字元（如 <script>），避免 XSS 攻擊或資料庫問題。
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "帳號只能包含英文字母、數字和底線", "username_value": username},
        )

    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "密碼長度至少 8 個字元", "username_value": username},
        )

    # --- 業務邏輯 ---

    # 為什麼要先查帳號是否存在，而不是直接建立讓資料庫報錯？
    # 因為資料庫報錯的訊息對使用者不友善（會是英文的 UNIQUE constraint 錯誤），
    # 我們想給使用者看到清楚的中文提示「此帳號已被使用」。
    existing_user = await auth_service.get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "此帳號已被使用", "username_value": username},
        )

    # 建立使用者（密碼會在 auth_service 裡被 bcrypt 雜湊後才存入資料庫）
    user = await auth_service.create_user(db, username, password)

    # 為什麼註冊完要自動登入？
    # 使用者體驗考量——註冊完還要再手動輸入一次帳號密碼去登入，很煩。
    # 在 session 中存入使用者資訊，之後每次請求 SessionMiddleware 會自動讀取。
    request.session["user_id"] = user.id
    request.session["username"] = user.username

    logger.info(f"使用者註冊成功並自動登入：{username}")

    # 為什麼回傳 RedirectResponse 而不是直接渲染首頁？
    # 因為 POST 請求完成後應該用「重新導向」（Post/Redirect/Get 模式）。
    # 如果直接渲染首頁，使用者按 F5 重新整理會再送一次 POST，導致重複註冊。
    # 用 302 導向的話，重新整理只會重送 GET /，不會重複送表單。
    return RedirectResponse(url="/", status_code=302)


# === 登入 ===


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "",       # 登入成功後要導回的頁面（從 URL ?next=... 取得）
    expired: str = "",    # 是否因 session 過期被導向（"1" = 是）
) -> HTMLResponse:
    """顯示登入頁面。支援 next（導回原頁面）和 expired（過期提示）參數。"""
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)

    context = {}

    # 為什麼需要 expired 參數？
    # 讓使用者知道「為什麼突然跳到登入頁」。
    # 如果沒提示，使用者會以為系統壞了。
    if expired == "1":
        context["error"] = "登入已過期，請重新登入"

    # 為什麼需要 next 參數？
    # 記住使用者「原本想去哪」。例如使用者想看 /meetings/abc 但沒登入，
    # 被導到 /login?next=/meetings/abc，登入成功後自動跳回 /meetings/abc。
    # 如果不記住，登入後一律跳首頁，使用者還要自己再點進去，很不方便。
    if next:
        context["next_url"] = next

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=context,
    )


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),         # 從表單隱藏欄位取得，登入後導向的路徑
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """處理登入表單。

    流程：驗證帳密 → 成功就建立 session 並導向 next 或首頁 → 失敗就重新顯示登入頁。
    """

    # authenticate_user 會去資料庫查帳號、比對密碼雜湊
    # 成功回傳 User 物件，失敗回傳 None
    user, status = await auth_service.authenticate_user(db, username, password)

    if not user:
        # 根據狀態顯示不同訊息
        if status == "deactivated":
            # 被停用帳號：顯示專屬訊息（不洩漏帳號存在，但告知原因）
            error_msg = "帳號已被停用，請聯繫管理員"
        else:
            # 帳號不存在或密碼錯誤：統一訊息（防止帳號枚舉攻擊）
            error_msg = "帳號或密碼錯誤"

        context = {"error": error_msg}
        if next:
            context["next_url"] = next
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context,
        )

    # 登入成功：建立 session
    request.session["user_id"] = user.id
    request.session["username"] = user.username

    logger.info(f"使用者登入成功：{username}")

    # 有 next → 導回原頁面，沒有 → 導向首頁
    redirect_url = next if next else "/"
    return RedirectResponse(url=redirect_url, status_code=302)


# === 登出 ===


@router.post("/logout")
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),  # 未登入會被攔截，走不到這裡
):
    """登出：清空 session → 導向登入頁。"""
    username = current_user.get("username", "unknown")

    # 清空 session = 伺服器忘記你是誰
    # 下次請求時 Cookie 裡的 session ID 已經對不到任何資料，等於「沒登入」
    request.session.clear()

    logger.info(f"使用者登出：{username}")
    return RedirectResponse(url="/login", status_code=302)
