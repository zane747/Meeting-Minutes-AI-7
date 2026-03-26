"""應用程式環境設定管理。

使用 pydantic-settings 從 .env 檔案讀取環境變數，
提供型別安全的設定存取。
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """應用程式設定。

    所有設定皆可透過環境變數或 .env 檔案覆寫。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # === Provider 切換 ===
    MODEL_MODE: str = "remote"

    # === Gemini（遠端模式）===
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # === GPU / Device ===
    DEVICE: str = "auto"  # "auto" | "cpu" | "cuda"

    # === Whisper（本地模式）===
    WHISPER_MODEL: str = "medium"
    WHISPER_MODEL_FALLBACK_ORDER: str = "medium,small,base,tiny"

    @property
    def whisper_fallback_list(self) -> list[str]:
        """取得 Whisper 模型降級順序列表。"""
        return [m.strip() for m in self.WHISPER_MODEL_FALLBACK_ORDER.split(",") if m.strip()]

    # === Diarization（說話者辨識，可選）===
    DIARIZATION_ENABLED: bool = False
    HF_TOKEN: str = ""
    DIARIZATION_DEFAULT_NUM_SPEAKERS: int = 0  # 0 = 自動偵測

    # === Ollama（本地摘要，可選）===
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_NUM_CTX: int = 32768
    OLLAMA_NUM_THREAD: int = 0  # 0 = 自動（Ollama 預設），建議設為 CPU 核心數如 16
    OLLAMA_GPU: str = "auto"  # "auto" = 自動偵測 | "true" = 強制 GPU | "false" = 強制 CPU

    @field_validator("OLLAMA_GPU")
    @classmethod
    def validate_ollama_gpu(cls, v: str) -> str:
        """驗證 OLLAMA_GPU 為有效的三態值（向後相容舊版布林格式）。"""
        # 向後相容：舊版 .env 的 "1"/"0" 布林格式
        compat_map = {"1": "true", "0": "false"}
        normalized = compat_map.get(v.strip(), v.lower().strip())
        if normalized not in {"auto", "true", "false"}:
            raise ValueError("OLLAMA_GPU 必須為 'auto'、'true' 或 'false'")
        return normalized

    # === 通用 ===
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 300
    DATABASE_URL: str = "sqlite+aiosqlite:///./meeting_minutes.db"

    @property
    def max_file_size_bytes(self) -> int:
        """取得檔案大小上限（bytes）。"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
