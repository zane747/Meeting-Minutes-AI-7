"""GeminiProvider：透過 Gemini API 處理音檔（遠端多模態）。

利用 Gemini 原生多模態能力，將音檔直接傳送至 API，
單一 Prompt 同時回傳逐字稿、摘要與 Action Items。
支援 ProcessingContext：跳過轉錄 / 注入 RTTM 說話者資訊。
"""

import json
import logging
from datetime import date

import google.generativeai as genai

from app.core.exceptions import (
    AuthenticationError,
    ProcessingError,
    RateLimitError,
)
from app.services.providers.base import (
    AudioProcessor,
    ProcessingContext,
    ProcessingResult,
)

logger = logging.getLogger(__name__)

GEMINI_AUDIO_PROMPT = """你是一位專業的會議記錄助理。今天的日期是 {today}。請分析以下音檔，並以 JSON 格式回傳：

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

GEMINI_AUDIO_WITH_SPEAKERS_PROMPT = """你是一位專業的會議記錄助理。今天的日期是 {today}。請分析以下音檔，並以 JSON 格式回傳。

以下是已知的說話者時間分佈，請在逐字稿中標示說話者：
{speakers_info}

請回傳：
1. transcript：逐字稿，格式：[MM:SS - MM:SS] [Speaker_X] 內容
2. summary：會議摘要（Markdown 格式），包含會議主題、重點討論事項、決議事項
3. action_items：待辦事項列表，每項包含 description、assignee、due_date
4. suggested_title：簡短標題

所有輸出必須使用繁體中文。

請嚴格以 JSON 格式回傳：
{{"suggested_title": "...", "transcript": "...", "summary": "...", "action_items": [...]}}"""

GEMINI_SUMMARY_PROMPT = """你是一位專業的會議記錄助理。今天的日期是 {today}。以下是一段會議的逐字稿，請分析後以 JSON 格式回傳：

1. summary：會議摘要（Markdown 格式），包含會議主題、重點討論事項、決議事項
2. action_items：待辦事項列表，每項包含 description、assignee（null 若無法辨識）、due_date（null 若未提及）
3. suggested_title：簡短標題

所有輸出必須使用繁體中文。

逐字稿：
{transcript}

請嚴格以 JSON 格式回傳：
{{"suggested_title": "...", "summary": "...", "action_items": [...]}}"""


class GeminiProvider(AudioProcessor):
    """透過 Gemini API 處理音檔（遠端多模態）。

    支援 ProcessingContext：
    - 有 TextGrid 逐字稿 + skip_transcription → 僅用文字 Prompt 做摘要
    - 有 RTTM speakers → 將說話者資訊注入 Prompt
    - 無 context → 照常多模態處理

    Args:
        api_key: Gemini API Key。
        model: Gemini 模型名稱。
    """

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        """初始化 GeminiProvider。

        Args:
            api_key: Gemini API Key。
            model: Gemini 模型名稱。
        """
        self._api_key = api_key
        self._model_name = model
        genai.configure(api_key=api_key)

    async def process(
        self, file_path: str, context: ProcessingContext | None = None
    ) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        Args:
            file_path: 音訊檔案的路徑。
            context: 標註檔上下文，可選。

        Returns:
            包含逐字稿、摘要與待辦事項的 ProcessingResult。

        Raises:
            RateLimitError: API 頻率受限（429）。
            AuthenticationError: API Key 無效（401）。
            ProcessingError: 其他處理失敗。
        """
        try:
            # A) 有 TextGrid 逐字稿 + 跳過轉錄 → 純文字摘要
            if context and context.skip_transcription and context.transcript:
                return await self._summarize_transcript(context.transcript)

            # B) 有 RTTM speakers → 注入說話者資訊至 Prompt
            if context and context.speakers:
                return await self._process_with_speakers(file_path, context.speakers)

            # C) 無 context → 照常多模態處理
            return await self._process_audio(file_path)

        except (RateLimitError, AuthenticationError):
            raise
        except Exception as e:
            self._handle_api_error(e)

    async def _process_audio(self, file_path: str) -> ProcessingResult:
        """標準多模態音檔處理。

        Args:
            file_path: 音訊檔案路徑。

        Returns:
            ProcessingResult。
        """
        logger.info(f"上傳音檔至 Gemini File API：{file_path}")
        audio_file = genai.upload_file(file_path)

        prompt = GEMINI_AUDIO_PROMPT.format(today=date.today().isoformat())
        logger.info(f"發送多模態 Prompt 至 {self._model_name}")
        model = genai.GenerativeModel(self._model_name)
        response = model.generate_content(
            [prompt, audio_file],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)
        logger.info("Gemini 多模態處理完成")
        return self._parse_result(result)

    async def _process_with_speakers(
        self, file_path: str, speakers: list[dict]
    ) -> ProcessingResult:
        """帶 RTTM 說話者資訊的音檔處理。

        Args:
            file_path: 音訊檔案路徑。
            speakers: RTTM 說話者片段列表。

        Returns:
            ProcessingResult（帶角色標籤的逐字稿）。
        """
        speakers_info = "\n".join(
            f"- {s['speaker']}: {s['start']:.1f}s ~ {s['end']:.1f}s"
            for s in speakers
        )
        prompt = GEMINI_AUDIO_WITH_SPEAKERS_PROMPT.format(
            speakers_info=speakers_info,
            today=date.today().isoformat(),
        )

        logger.info(f"上傳音檔至 Gemini File API（含 RTTM）：{file_path}")
        audio_file = genai.upload_file(file_path)

        model = genai.GenerativeModel(self._model_name)
        response = model.generate_content(
            [prompt, audio_file],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)
        logger.info("Gemini 處理完成（含 RTTM 角色）")
        return self._parse_result(result)

    async def _summarize_transcript(self, transcript: str) -> ProcessingResult:
        """僅用文字逐字稿做摘要（跳過音檔轉錄）。

        Args:
            transcript: TextGrid 匯入的逐字稿。

        Returns:
            ProcessingResult（transcript 來自 TextGrid，summary 由 AI 生成）。
        """
        prompt = GEMINI_SUMMARY_PROMPT.format(transcript=transcript, today=date.today().isoformat())

        logger.info("發送純文字 Prompt 至 Gemini（跳過轉錄）")
        model = genai.GenerativeModel(self._model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)
        logger.info("Gemini 摘要生成完成")

        return ProcessingResult(
            suggested_title=result.get("suggested_title"),
            transcript=transcript,
            summary=result.get("summary", ""),
            action_items=result.get("action_items", []),
        )

    @staticmethod
    def _parse_result(result: dict) -> ProcessingResult:
        """將 Gemini JSON 回應解析為 ProcessingResult。

        Args:
            result: Gemini 回應的 JSON dict。

        Returns:
            ProcessingResult。
        """
        return ProcessingResult(
            suggested_title=result.get("suggested_title"),
            transcript=result.get("transcript", ""),
            summary=result.get("summary", ""),
            action_items=result.get("action_items", []),
        )

    @staticmethod
    def _handle_api_error(e: Exception) -> None:
        """分類並拋出對應的自定義例外。

        Args:
            e: 原始例外。

        Raises:
            RateLimitError: 429 錯誤。
            AuthenticationError: 401 錯誤。
            ProcessingError: 其他錯誤。
        """
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
