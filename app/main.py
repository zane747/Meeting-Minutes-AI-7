"""FastAPI 應用程式入口。"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理。

    啟動時：初始化資料庫、建立 uploads 目錄、檢查 Provider 可用性。
    """
    # --- Startup ---
    # GPU 環境偵測
    from app.services.device_manager import DeviceManager

    DeviceManager.initialize()

    await init_db()
    logger.info("資料庫初始化完成")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"上傳目錄已確認：{upload_dir}")

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

# 靜態資源
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)

# 註冊路由
from app.api.routes import meetings, pages, system

app.include_router(meetings.router)
app.include_router(pages.router)
app.include_router(system.router)
