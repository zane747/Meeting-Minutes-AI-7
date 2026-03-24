"""LocalWhisperProvider：透過本地端 Whisper 模型處理音檔。

使用 OpenAI Whisper 進行語音轉錄（Lazy Load + 快取模式）。
逐字稿保留原始語言，不強制轉為繁體中文。
若已配置 Ollama，可選配本地摘要功能（使用 Gemma 2 9B）。
"""

import json
import logging

import httpx

from app.config import settings
from app.core.exceptions import ProcessingError, ProviderUnavailableError
from app.services.providers.base import AudioProcessor, ProcessingResult

logger = logging.getLogger(__name__)

OLLAMA_SUMMARY_PROMPT = """你是一位專業的會議記錄助理。以下是一段會議的逐字稿，請分析後以 JSON 格式回傳：

1. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
2. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
3. suggested_title：根據會議內容建議一個簡短標題

所有輸出必須使用繁體中文。

逐字稿：
{transcript}

請嚴格以下列 JSON 格式回傳：
{{
  "suggested_title": "...",
  "summary": "...",
  "action_items": [
    {{"description": "...", "assignee": "..." or null, "due_date": "..." or null}}
  ]
}}"""


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

    async def _generate_summary_with_ollama(
        self, transcript: str
    ) -> dict | None:
        """透過 Ollama API 生成摘要與 Action Items。

        Args:
            transcript: 逐字稿文字。

        Returns:
            包含 summary、action_items、suggested_title 的字典，或 None（若失敗）。
        """
        if not settings.OLLAMA_ENABLED:
            return None

        prompt = OLLAMA_SUMMARY_PROMPT.format(transcript=transcript)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                    },
                )
                response.raise_for_status()

            result = response.json()
            return json.loads(result["response"])

        except Exception as e:
            logger.warning(f"Ollama 摘要生成失敗：{e}")
            return None

    async def process(self, file_path: str) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        Args:
            file_path: 音訊檔案的路徑。

        Returns:
            包含逐字稿（及可選的摘要與 Action Items）的 ProcessingResult。

        Raises:
            ProviderUnavailableError: Whisper 未安裝。
            ProcessingError: 轉錄失敗。
        """
        try:
            self._load_model()

            logger.info(f"開始轉錄音檔：{file_path}")
            result = LocalWhisperProvider._model.transcribe(file_path)

            transcript = self._format_transcript(result.get("segments", []))
            logger.info("Whisper 轉錄完成")

            # 嘗試透過 Ollama 生成摘要
            summary_result = await self._generate_summary_with_ollama(transcript)

            if summary_result:
                logger.info("Ollama 摘要生成完成")
                return ProcessingResult(
                    suggested_title=summary_result.get("suggested_title"),
                    transcript=transcript,
                    summary=summary_result.get("summary", ""),
                    action_items=summary_result.get("action_items", []),
                )

            # 無 Ollama → 僅回傳逐字稿
            return ProcessingResult(
                transcript=transcript,
            )

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
