"""GeminiProvider：透過 Gemini API 處理音檔（遠端多模態）。

利用 Gemini 原生多模態能力，將音檔直接傳送至 API，
單一 Prompt 同時回傳逐字稿、摘要與 Action Items。
"""

import json
import logging

import google.generativeai as genai

from app.core.exceptions import (
    AuthenticationError,
    ProcessingError,
    RateLimitError,
)
from app.services.providers.base import AudioProcessor, ProcessingResult

logger = logging.getLogger(__name__)

GEMINI_PROMPT = """你是一位專業的會議記錄助理。請分析以下音檔，並以 JSON 格式回傳：

1. transcript：逐字稿，以段落式時間戳記呈現（格式：[MM:SS - MM:SS] 內容）
2. summary：會議摘要（Markdown 格式），包含：
   - 會議主題
   - 重點討論事項
   - 決議事項
3. action_items：待辦事項列表，每項包含 description、assignee（若無法辨識則為 null）、due_date（若未提及則為 null）
4. suggested_title：根據會議內容建議一個簡短標題

所有輸出必須使用繁體中文。

請嚴格以下列 JSON 格式回傳：
{
  "suggested_title": "...",
  "transcript": "...",
  "summary": "...",
  "action_items": [
    {"description": "...", "assignee": "..." or null, "due_date": "..." or null}
  ]
}"""


class GeminiProvider(AudioProcessor):
    """透過 Gemini API 處理音檔（遠端多模態）。

    Args:
        api_key: Gemini API Key。
        model: Gemini 模型名稱。
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        """初始化 GeminiProvider。

        Args:
            api_key: Gemini API Key。
            model: Gemini 模型名稱。
        """
        self._api_key = api_key
        self._model_name = model
        genai.configure(api_key=api_key)

    async def process(self, file_path: str) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        Args:
            file_path: 音訊檔案的路徑。

        Returns:
            包含逐字稿、摘要與待辦事項的 ProcessingResult。

        Raises:
            RateLimitError: API 頻率受限（429）。
            AuthenticationError: API Key 無效（401）。
            ProcessingError: 其他處理失敗。
        """
        try:
            logger.info(f"上傳音檔至 Gemini File API：{file_path}")
            audio_file = genai.upload_file(file_path)

            logger.info(f"發送 Prompt 至 {self._model_name}")
            model = genai.GenerativeModel(self._model_name)
            response = model.generate_content(
                [GEMINI_PROMPT, audio_file],
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                ),
            )

            result = json.loads(response.text)
            logger.info("Gemini 處理完成")

            return ProcessingResult(
                suggested_title=result.get("suggested_title"),
                transcript=result.get("transcript", ""),
                summary=result.get("summary", ""),
                action_items=result.get("action_items", []),
            )

        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg:
                raise RateLimitError(
                    "API 頻率受限，請稍候或切換本地模式"
                ) from e
            if "401" in error_msg or "unauthorized" in error_msg:
                raise AuthenticationError(
                    "API Key 設定錯誤，請檢查 .env 設定"
                ) from e
            raise ProcessingError(f"Gemini 處理失敗：{e}") from e

    def get_provider_name(self) -> str:
        """回傳 Provider 名稱。"""
        return "Gemini API (Remote)"

    async def health_check(self) -> bool:
        """測試 API Key 有效性。

        Returns:
            True 表示 API Key 有效且可連線。
        """
        try:
            model = genai.GenerativeModel(self._model_name)
            model.count_tokens("test")
            return True
        except Exception as e:
            logger.warning(f"Gemini 健康檢查失敗：{e}")
            return False
