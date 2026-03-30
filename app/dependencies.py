"""依賴注入工廠函式。

【新手導讀】「依賴注入」（Dependency Injection, DI）是 FastAPI 的核心功能之一。
簡單說就是：路由函式「宣告」自己需要什麼，FastAPI 自動幫你準備好。

例如：
    @router.get("/meetings")
    async def list_meetings(user = Depends(get_current_user)):
        ...

FastAPI 看到 Depends(get_current_user)，就會：
1. 先執行 get_current_user 函式
2. 如果成功，把結果（使用者資訊）傳給 list_meetings
3. 如果失敗（未登入），直接回傳錯誤，list_meetings 根本不會被執行

這就像辦公室門口的門禁——你要先刷卡（get_current_user），
刷過了才能進去（執行路由函式）。
"""

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.services.providers.base import AudioProcessor
from app.services.providers.gemini_provider import GeminiProvider
from app.services.providers.local_whisper_provider import LocalWhisperProvider


def get_audio_processor(mode: str | None = None) -> AudioProcessor:
    """根據前端參數或環境變數，實例化對應的 Provider。

    Args:
        mode: 前端傳來的模式（"remote" / "local"），若為 None 則使用環境變數。

    Returns:
        AudioProcessor 的具體實作。

    Raises:
        ValueError: 當模式設定值無效時。
    """
    effective_mode = mode or settings.MODEL_MODE

    if effective_mode == "remote": ##如果模式是 remote，就回傳 GeminiProvider 的實例，並帶入 API 金鑰和模型名稱
        return GeminiProvider( ## GeminiProvider 是一個實作了 AudioProcessor 的類別，專門用來跟 Google Gemini API 互動
            api_key=settings.GEMINI_API_KEY,  ## 從環境變數讀取 API 金鑰，確保安全性（不把金鑰寫死在程式碼裡）
            model=settings.GEMINI_MODEL, ## 從環境變數讀取要使用的 Gemini 模型名稱，例如 "gemini-1.5-pro" 或 "gemini-2.0-pro"
        )
    elif effective_mode == "local":
        return LocalWhisperProvider(
            model_size=settings.WHISPER_MODEL,
        )
    else:
        raise ValueError(f"未知的 MODEL_MODE：{effective_mode}") 


# === 認證依賴函式 ===


async def get_current_user(request: Request) -> dict:
    """從 Session 取得當前登入的使用者資訊。

    【新手導讀】這個函式是整個認證系統的「守門員」。
    它會在每個需要登入的路由被呼叫之前先執行：

    1. 從 request.session 中讀取 user_id（session 資料由 SessionMiddleware 管理）
    2. 如果有 user_id → 表示使用者已登入，回傳使用者資訊
    3. 如果沒有 user_id → 表示未登入：
       - 頁面路由：302 重導到 /login（帶上 next 參數，登入後導回原頁面）
       - API 路由：回傳 401 Unauthorized

    Args:
        request: FastAPI 的 Request 物件，包含 session、URL 等資訊。

    Returns:
        包含 user_id 和 username 的字典。

    Raises:
        HTTPException: 當 API 路由未登入時回傳 401。
    """
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    if user_id and username:
        # 查資料庫確認帳號仍為啟用狀態
        # 為什麼要每次都查？因為帳號可能在另一個使用者的操作中被停用，
        # session 裡的資料不會自動更新，必須去資料庫確認。
        from app.models.database_models import User
        async with async_session() as db:
            user = await db.get(User, user_id)
            if not user or not user.is_active:
                # 帳號已被停用或刪除 → 清除 session，當作未登入處理
                request.session.clear()
                # 不直接 return，讓下面的「未登入邏輯」處理導向
                user_id = None
                username = None

    if user_id and username:
        return {"user_id": user_id, "username": username}

    # 未登入的處理邏輯：根據路由類型決定回應方式
    request_path = request.url.path

    if request_path.startswith("/api/"):
        # API 路由：回傳 401 JSON 錯誤（給 JavaScript/HTMX 處理）
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="未登入，請先登入系統",
        )
    else:
        # 頁面路由：302 重導到登入頁（帶上 next 參數和 expired 提示）
        # 如果 session 曾經有資料但現在沒了，可能是過期了
        redirect_url = f"/login?next={request_path}"
        raise HTTPException(
            status_code=307,
            detail="需要登入",
            headers={"Location": redirect_url},
        )


async def get_current_user_optional(request: Request) -> dict | None:
    """從 Session 取得當前使用者資訊（允許未登入）。

    【新手導讀】跟 get_current_user 類似，但不會擋人。
    用在「已登入和未登入都能訪問」的頁面（例如登入頁本身）。
    - 已登入 → 回傳使用者資訊
    - 未登入 → 回傳 None（不會報錯）

    Args:
        request: FastAPI 的 Request 物件。

    Returns:
        使用者資訊字典，或 None（未登入時）。
    """
    user_id = request.session.get("user_id")
    username = request.session.get("username")

    if user_id and username:
        return {"user_id": user_id, "username": username}
    return None
