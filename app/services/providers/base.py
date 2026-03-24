"""AudioProcessor 抽象介面與 ProcessingResult 資料結構。

定義所有 Provider 必須實作的介面，確保主程式與具體模型實作解耦。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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
    新增 Provider 時不需修改現有程式碼（開放封閉原則）。
    """

    @abstractmethod
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
