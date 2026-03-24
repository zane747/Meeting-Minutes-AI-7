"""AudioProcessor 抽象介面、ProcessingContext 與 ProcessingResult 資料結構。

定義所有 Provider 必須實作的介面，確保主程式與具體模型實作解耦。
ProcessingContext 攜帶標註檔（TextGrid/RTTM）解析後的上下文資訊。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ProcessingContext:
    """標註檔解析後的上下文資訊。

    由 AnnotationService 解析 TextGrid/RTTM 後組裝，
    傳入 Provider 影響處理行為。

    Attributes:
        transcript: TextGrid 匯入的逐字稿（帶時間戳記）。
        speakers: RTTM 解析的說話者片段列表。
        skip_transcription: 使用者選擇跳過 AI 轉錄，使用 TextGrid 逐字稿。
    """

    transcript: str | None = None
    speakers: list[dict] | None = None
    skip_transcription: bool = False


@dataclass
class ProcessingResult:
    """AI 處理結果的統一資料結構。

    Attributes:
        suggested_title: AI 建議的會議標題。
        transcript: 段落式時間戳記逐字稿。
        summary: Markdown 格式的會議摘要。
        action_items: 待辦事項列表。
    """

    suggested_title: str | None = None
    transcript: str = ""
    summary: str = ""
    action_items: list[dict] = field(default_factory=list)


class AudioProcessor(ABC):
    """音檔處理的抽象介面（Strategy Interface）。

    所有 Provider 必須實作此介面，確保主程式與具體模型實作解耦。
    context 參數預設為 None，既有呼叫方式不受影響。
    """

    @abstractmethod
    async def process(
        self, file_path: str, context: ProcessingContext | None = None
    ) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        Args:
            file_path: 音訊檔案的路徑。
            context: 標註檔上下文（TextGrid 逐字稿、RTTM 說話者），可選。

        Returns:
            包含逐字稿、摘要與待辦事項的 ProcessingResult。

        Raises:
            RateLimitError: API 頻率受限（429）。
            AuthenticationError: API Key 無效（401）。
            ProcessingError: 其他處理失敗。
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """回傳 Provider 名稱，用於日誌與 UI 顯示。

        Returns:
            Provider 的顯示名稱。
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """檢查 Provider 是否可用（API 連通性、模型可用性）。

        Returns:
            True 表示可用，False 表示不可用。
        """
        ...
