"""FastAPI 應用程式入口。

【新手導讀】這是整個應用程式的「大門」。
FastAPI 啟動時會執行這個檔案，它負責：
1. 建立 FastAPI app 物件
2. 設定中間件（Middleware）— 像大樓的門禁，每個請求都要經過
3. 掛載靜態資源（CSS、JS 檔案）
4. 註冊路由（告訴 FastAPI「哪個 URL 對應哪個函式」）
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette_session import SessionMiddleware

from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理。

    啟動時：初始化資料庫、建立 uploads 目錄、檢查 Provider 可用性。
    """
    # --- Startup ---
    await init_db() ## 初始化資料庫連線、建立表格等，確保應用程式啟動後能正常使用資料庫
    logger.info("資料庫初始化完成")

    upload_dir = Path(settings.UPLOAD_DIR) ##創建了一個用於存放上傳文件的目錄路徑對象 確保檔案格式跟大小正確
    upload_dir.mkdir(parents=True, exist_ok=True)##如果該目錄不存在，則創建它（parents=True 允許創建多層目錄，exist_ok=True 表示如果目錄已存在則不報錯）
    logger.info(f"上傳目錄已確認：{upload_dir}")##  記錄上傳目錄的路徑，方便調試和確認目錄是否正確創建
    

    # Provider 健康檢查（啟動時 warning）
    try: 
        from app.dependencies import get_audio_processor

        processor = get_audio_processor()
        is_healthy = await processor.health_check()
        if is_healthy:
            logger.info(f"Provider {processor.get_provider_name()} 可用")
        else:
            logger.warning(f"Provider {processor.get_provider_name()} 不可用")
    except Exception as e:
        logger.warning(f"Provider 健康檢查失敗：{e}")

    yield

    # --- Shutdown ---
    logger.info("應用程式關閉")


app = FastAPI(
    title="Meeting Minutes AI",
    description="AI 驅動的會議紀錄應用程式",
    version="0.1.0",
    lifespan=lifespan,
)

# === Session 中間件 ===
# 【新手導讀】Middleware（中間件）就像大樓的門禁系統——
# 每一個進出大樓的人都要經過它。SessionMiddleware 的工作是：
# 1. 收到請求時：從 Cookie 讀取 session ID，載入對應的 session 資料
# 2. 回傳回應時：把 session 資料存起來，並在 Cookie 中寫入 session ID
#
# secret_key 是用來「簽名」Cookie 的密鑰，防止使用者竄改 Cookie 內容。
# max_age 是 session 的有效期（秒），86400 秒 = 24 小時。
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    cookie_name="session",
    max_age=86400,  # 24 小時
    same_site="lax",
    https_only=False,  # 開發環境用 HTTP，正式環境應改為 True
)

# 靜態資源
app.mount( ##把 static 目錄掛載到 /static 路徑，讓瀏覽器能訪問 CSS、JS 等靜態檔案
    "/static", ## URL 路徑前綴，訪問靜態資源時需要加上 /static，例如 /static/style.css
    StaticFiles(directory=Path(__file__).parent / "static"), #  靜態資源所在的目錄，這裡是 app/static
    name="static", ## 這個名稱在 FastAPI 中用於內部識別，可以隨意取，但通常會用 "static"
)

# 註冊路由
# 【新手導讀】include_router 就是告訴 FastAPI「把這組路由加進來」。
# 順序很重要：auth 要在 pages 前面，因為 /login、/register 路由
# 不需要認證，要優先被匹配到。
from app.api.routes import accounts, auth, meetings, pages

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(meetings.router)
app.include_router(pages.router)
