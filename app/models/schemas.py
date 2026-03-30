"""Pydantic 請求/回應模型定義。

【新手導讀】Pydantic 模型用來定義「資料的格式規範」。
當使用者送出表單或 API 請求時，Pydantic 會自動幫你：
1. 檢查資料格式是否正確（例如帳號是否符合規則）
2. 如果不正確，自動回傳錯誤訊息

術語解釋：
- BaseModel：Pydantic 的基礎類別，所有資料模型都繼承它。
- Field(...)：定義欄位的驗證規則（最小長度、正則表達式等）。
- model_config：設定模型的行為（例如是否能從 ORM 物件轉換）。

注意：ProcessingResult 定義在 app/services/providers/base.py，
作為 Provider 回傳的內部資料結構，不在此處重複。
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# === Auth Schemas（認證相關）===


class UserCreate(BaseModel):
    """使用者註冊的請求模型。

    【新手導讀】當使用者填寫註冊表單按下送出，
    瀏覽器會把 username 和 password 送到伺服器。
    這個 class 負責「檢查這些資料是否合格」。

    驗證規則：
    - username：3~30 字元，只允許英文字母、數字、底線
    - password：至少 8 字元
    """

    username: str = Field(
        ...,  # ... 表示「必填」
        min_length=3,
        max_length=30,
        description="帳號名稱（3~30 字元，英數字與底線）",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="密碼（至少 8 字元）",
    )

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        """驗證帳號格式：只允許英文字母、數字、底線。

        Args:
            v: 使用者輸入的帳號。

        Returns:
            通過驗證的帳號。

        Raises:
            ValueError: 帳號格式不符。
        """
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("帳號只能包含英文字母、數字和底線")
        return v


class UserLogin(BaseModel):
    """使用者登入的請求模型。

    登入時不需要嚴格驗證格式（只要非空即可），
    因為我們會直接拿去跟資料庫比對。
    """

    username: str
    password: str


# === Action Item Schemas ===


class ActionItemCreate(BaseModel):
    """新增 Action Item 的請求模型。"""

    description: str
    assignee: str | None = None
    due_date: str | None = None


class ActionItemUpdate(BaseModel):
    """編輯 Action Item 的請求模型。"""

    description: str | None = None
    assignee: str | None = None
    due_date: str | None = None
    is_completed: bool | None = None


class ActionItemResponse(BaseModel):
    """Action Item 回應模型。"""

    id: str
    meeting_id: str
    description: str
    assignee: str | None
    due_date: str | None
    is_completed: bool

    model_config = {"from_attributes": True}


# === Meeting Schemas ===


class MeetingCreate(BaseModel):
    """上傳時的請求模型（multipart form 輔助）。"""

    title: str | None = None
    mode: str | None = None
    duration: float = 0.0


class MeetingUpdate(BaseModel):
    """編輯會議的請求模型。"""

    title: str | None = None
    transcript: str | None = None
    summary: str | None = None


class MeetingResponse(BaseModel):
    """會議完整回應模型。"""

    id: str
    title: str | None
    file_name: str
    file_path: str | None
    file_size: int
    duration: float
    status: str
    provider: str | None
    transcript: str | None
    summary: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    action_items: list[ActionItemResponse] = []

    model_config = {"from_attributes": True}


class MeetingStatusResponse(BaseModel):
    """狀態輪詢回應模型（供 HTMX polling）。"""

    id: str
    status: str
    provider: str | None
    error_message: str | None
    progress_step: str | None = None

    model_config = {"from_attributes": True}


class MeetingListItem(BaseModel):
    """會議列表項目（歷史紀錄頁用）。"""

    id: str
    title: str | None
    file_name: str
    duration: float
    status: str
    provider: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# === 通用回應 ===


class MessageResponse(BaseModel):
    """通用訊息回應模型。"""

    detail: str


class UploadResponse(BaseModel):
    """上傳+處理觸發後的回應模型。"""

    meeting_id: str
    status: str
