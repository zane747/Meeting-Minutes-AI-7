"""應用程式環境設定管理。

使用 pydantic-settings 從 .env 檔案讀取環境變數，
提供型別安全的設定存取。
"""

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

    # === Whisper（本地模式）===
    WHISPER_MODEL: str = "base"

    # === Ollama（本地摘要，可選）===
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma2:9b"

    # === 通用 ===
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 300
    DATABASE_URL: str = "sqlite+aiosqlite:///./meeting_minutes.db"

    @property
    def max_file_size_bytes(self) -> int:
        """取得檔案大小上限（bytes）。"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


settings = Settings()
