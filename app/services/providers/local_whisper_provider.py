"""LocalWhisperProvider：透過本地端 Whisper 模型處理音檔。

使用 OpenAI Whisper 進行語音轉錄（Lazy Load + 快取模式）。
逐字稿保留原始語言，不強制轉為繁體中文。
若已配置 Ollama，可選配本地摘要功能（使用 Gemma 2 9B）。
"""

import logging

from app.config import settings
from app.core.exceptions import ProcessingError, ProviderUnavailableError
from app.services.providers.base import (
    AudioProcessor,
    ProcessingContext,
    ProcessingResult,
)
from app.services.annotation_service import merge_transcript_with_speakers

logger = logging.getLogger(__name__)


class LocalWhisperProvider(AudioProcessor):
    """透過本地端 Whisper 模型處理音檔。

    Args:
        model_size: Whisper 模型大小（tiny/base/small/medium/large）。
    """

    _model = None  # 類別層級快取，Lazy Load
    _cached_model_size: str | None = None  # 記錄快取的模型大小

    def __init__(self, model_size: str = "base") -> None:
        """初始化 LocalWhisperProvider。

        Args:
            model_size: Whisper 模型大小。
        """
        self._model_size = model_size

    def _load_model(self) -> None:
        """Lazy Load Whisper 模型（首次呼叫時載入，之後快取）。

        若請求的模型大小與快取不同，會重新載入。

        Raises:
            ProviderUnavailableError: Whisper 套件未安裝。
        """
        if (
            LocalWhisperProvider._model is not None
            and LocalWhisperProvider._cached_model_size == self._model_size
        ):
            return

        try:
            import whisper

            logger.info(f"載入 Whisper 模型：{self._model_size}")
            LocalWhisperProvider._model = whisper.load_model(self._model_size)
            LocalWhisperProvider._cached_model_size = self._model_size
            logger.info("Whisper 模型載入完成")
        except ImportError:
            raise ProviderUnavailableError(
                "Whisper 未安裝，請執行 `pip install openai-whisper` 或切換遠端模式"
            )

    def _format_transcript(self, segments: list[dict]) -> str:
        """將 Whisper segments 格式化為段落式時間戳記逐字稿。

        Args:
            segments: Whisper 輸出的 segments 列表。

        Returns:
            格式化後的逐字稿文字。
        """
        lines = []
        for seg in segments:
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            text = seg["text"].strip()
            if text:
                lines.append(f"[{start} - {end}] {text}")
        return "\n".join(lines)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """將秒數格式化為 MM:SS。

        Args:
            seconds: 秒數。

        Returns:
            MM:SS 格式的時間字串。
        """
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    async def process(
        self, file_path: str, context: ProcessingContext | None = None
    ) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        支援 ProcessingContext：
        - 有 TextGrid 逐字稿 + skip_transcription → 跳過 Whisper
        - 有 RTTM speakers → 後處理合併角色標籤
        - 無 context → 照常 Whisper 轉錄

        Args:
            file_path: 音訊檔案的路徑。
            context: 標註檔上下文，可選。

        Returns:
            包含逐字稿（及可選的摘要與 Action Items）的 ProcessingResult。

        Raises:
            ProviderUnavailableError: Whisper 未安裝。
            ProcessingError: 轉錄失敗。
        """
        try:
            # A) 有 TextGrid 逐字稿 + 跳過轉錄
            if context and context.skip_transcription and context.transcript:
                logger.info("使用 TextGrid 逐字稿，跳過 Whisper 轉錄")
                transcript = context.transcript
            else:
                # B) Whisper 轉錄
                self._load_model()
                logger.info(f"開始轉錄音檔：{file_path}")
                result = LocalWhisperProvider._model.transcribe(file_path)
                transcript = self._format_transcript(result.get("segments", []))
                logger.info("Whisper 轉錄完成")

            # C) 有 RTTM speakers → 後處理合併角色標籤
            if context and context.speakers:
                transcript = merge_transcript_with_speakers(
                    transcript, context.speakers
                )
                logger.info("RTTM 角色標籤已合併至逐字稿")

            # D) Ollama 摘要（若可用）
            from app.services import ollama_service

            summary_result = (
                await ollama_service.generate_summary(transcript)
                if settings.OLLAMA_ENABLED
                else None
            )

            if summary_result:
                logger.info("Ollama 摘要生成完成")
                return ProcessingResult(
                    suggested_title=summary_result.get("suggested_title"),
                    transcript=transcript,
                    summary=summary_result.get("summary", ""),
                    action_items=summary_result.get("action_items", []),
                )

            # 無 Ollama → 僅回傳逐字稿
            return ProcessingResult(transcript=transcript)

        except ProviderUnavailableError:
            raise
        except Exception as e:
            raise ProcessingError(f"Whisper 處理失敗：{e}") from e

    def get_provider_name(self) -> str:
        """回傳 Provider 名稱。"""
        if settings.OLLAMA_ENABLED:
            return "Whisper + Ollama (Local)"
        return "Whisper (Local)"

    async def health_check(self) -> bool:
        """檢查 Whisper 套件與 Ollama 可用性。

        Returns:
            True 表示 Whisper 可用。
        """
        # 檢查 whisper 套件
        try:
            import whisper  # noqa: F401
        except ImportError:
            logger.warning("Whisper 套件未安裝")
            return False

        # 檢查 Ollama（若啟用）
        if settings.OLLAMA_ENABLED:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{settings.OLLAMA_BASE_URL}/api/tags"
                    )
                    resp.raise_for_status()
                    logger.info("Ollama 服務可用")
            except Exception as e:
                logger.warning(f"Ollama 服務不可用：{e}")

        return True
