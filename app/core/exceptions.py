"""自定義例外類別。"""


class ProviderUnavailableError(Exception):
    """Provider 不可用（未安裝或無法連線）。"""

    pass


class RateLimitError(Exception):
    """API 頻率受限（429）。"""

    pass


class AuthenticationError(Exception):
    """API Key 無效（401）。"""

    pass


class ProcessingError(Exception):
    """AI 處理失敗（通用錯誤）。"""

    pass
