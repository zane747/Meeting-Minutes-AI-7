"""依賴注入工廠函式。

透過 FastAPI Depends 機制，根據環境變數或前端參數動態實例化 Provider。
"""

from app.config import settings
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

    if effective_mode == "remote":
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    elif effective_mode == "local":
        return LocalWhisperProvider(
            model_size=settings.WHISPER_MODEL,
        )
    else:
        raise ValueError(f"未知的 MODEL_MODE：{effective_mode}")
