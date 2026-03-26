"""系統狀態 API 端點。

提供 GPU 偵測結果、目前運算模式、VRAM 使用量等系統資訊。
"""

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import SystemStatusResponse
from app.services.device_manager import DeviceManager

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """查詢系統運算資源狀態。"""
    status = DeviceManager.get_status()
    vram = DeviceManager.get_vram_info()

    return SystemStatusResponse(
        device=status["device"],
        gpu_available=status["gpu_available"],
        gpu_name=status["gpu_name"],
        gpu_vram_total_gb=vram["total_gb"],
        gpu_vram_used_gb=vram["used_gb"],
        whisper_model=settings.WHISPER_MODEL,
        whisper_active_model=status["whisper_active_model"],
        force_cpu_fallback=status["force_cpu_fallback"],
        last_fallback_reason=status["last_fallback_reason"],
        ollama_enabled=settings.OLLAMA_ENABLED,
        diarization_enabled=settings.DIARIZATION_ENABLED,
    )
