"""Pydantic 請求/回應模型定義。

注意：ProcessingResult 定義在 app/services/providers/base.py，
作為 Provider 回傳的內部資料結構，不在此處重複。
"""

from datetime import datetime

from pydantic import BaseModel


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
    progress: int = 0
    progress_stage: str | None = None

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


# === Speaker Schemas ===


class SpeakerResponse(BaseModel):
    """說話者回應模型。"""

    id: str
    meeting_id: str
    label: str
    display_name: str | None
    color: str | None
    key_points: str | None = None
    stance: str | None = None

    model_config = {"from_attributes": True}


class SpeakerUpdateRequest(BaseModel):
    """更新說話者名稱/顏色的請求模型。"""

    display_name: str | None = None
    color: str | None = None


# === Utterance Schemas ===


class UtteranceResponse(BaseModel):
    """發言段落回應模型。"""

    id: str
    meeting_id: str
    speaker_id: str | None
    speaker_label: str | None = None
    speaker_display_name: str | None = None
    speaker_color: str | None = None
    start_time: float
    end_time: float
    text: str
    intent_tag: str | None
    order_index: int

    model_config = {"from_attributes": True}


# === Topic Schemas ===


class TopicResponse(BaseModel):
    """主題段落回應模型。"""

    id: str
    meeting_id: str
    title: str
    start_time: float | None
    end_time: float | None
    order_index: int
    speakers_involved: str | None = None

    model_config = {"from_attributes": True}


# === System Status Schemas ===


class SystemStatusResponse(BaseModel):
    """系統運算資源狀態回應模型。"""

    device: str
    gpu_available: bool
    gpu_name: str | None = None
    gpu_vram_total_gb: float | None = None
    gpu_vram_used_gb: float | None = None
    whisper_model: str
    whisper_active_model: str | None = None
    force_cpu_fallback: bool
    last_fallback_reason: str | None = None
    ollama_enabled: bool
    diarization_enabled: bool


# === 通用回應 ===


class MessageResponse(BaseModel):
    """通用訊息回應模型。"""

    detail: str


class UploadResponse(BaseModel):
    """上傳+處理觸發後的回應模型。"""

    meeting_id: str
    status: str
