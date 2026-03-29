"""會議相關 REST API 路由。"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_audio_processor, get_current_user
from app.models.database_models import ActionItem, AnnotationFile, Meeting, MeetingStatus
from app.models.schemas import (
    ActionItemCreate,
    ActionItemResponse,
    ActionItemUpdate,
    MeetingListItem,
    MeetingResponse,
    MeetingStatusResponse,
    MeetingUpdate,
    MessageResponse,
    UploadResponse,
)
from app.services import annotation_service, audio_service, ollama_service
from app.services.meeting_processor import process_meeting
from app.services.providers.base import ProcessingContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.post("/upload-and-process", response_model=UploadResponse)
async def upload_and_process(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    textgrid: UploadFile | None = None,
    rttm: UploadFile | None = None,
    title: str | None = None,
    mode: str | None = Query(None),
    skip_transcription: bool = False,
    duration: float = 0.0,
) -> UploadResponse:
    """上傳音檔（+ TextGrid/RTTM 選填）+ 自動觸發 AI 處理。

    Args:
        file: 上傳的音檔（必要）。
        background_tasks: FastAPI 背景任務。
        db: 資料庫 Session。
        textgrid: TextGrid 標註檔（選填）。
        rttm: RTTM 角色辨識檔（選填）。
        title: 會議標題（選填）。
        mode: 處理模式（remote/local）。
        skip_transcription: 使用 TextGrid 逐字稿，跳過 AI 轉錄。
        duration: 前端傳來的音檔時長（秒）。

    Returns:
        包含 meeting_id 的回應。
    """
    # 驗證音檔
    try:
        audio_service.validate_audio_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 儲存音檔
    try:
        file_path, file_size = await audio_service.save_file(file)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 後端計算時長（若前端未提供）
    if duration <= 0:
        duration = audio_service.get_duration(file_path)

    # 決定 Provider
    effective_mode = mode or "remote"
    processor = get_audio_processor(effective_mode)

    # 建立 Meeting 紀錄
    meeting = Meeting(
        title=title,
        file_name=file.filename or "unknown",
        file_path=file_path,
        file_size=file_size,
        duration=duration,
        status=MeetingStatus.PROCESSING,
        provider=effective_mode,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    # 處理標註檔 → 組裝 ProcessingContext
    context = await _process_annotations(
        meeting.id, textgrid, rttm, skip_transcription, db
    )

    # 送入背景任務
    background_tasks.add_task(process_meeting, meeting.id, processor, context)

    return UploadResponse(meeting_id=meeting.id, status="processing")


async def _process_annotations(
    meeting_id: str,
    textgrid: UploadFile | None,
    rttm: UploadFile | None,
    skip_transcription: bool,
    db: AsyncSession,
) -> ProcessingContext | None:
    """處理標註檔並組裝 ProcessingContext。

    Args:
        meeting_id: 會議 ID。
        textgrid: TextGrid 檔案。
        rttm: RTTM 檔案。
        skip_transcription: 是否跳過轉錄。
        db: 資料庫 Session。

    Returns:
        ProcessingContext 或 None（無標註檔時）。
    """
    if not textgrid and not rttm:
        return None

    context = ProcessingContext(skip_transcription=skip_transcription)

    # 處理 TextGrid
    if textgrid:
        try:
            audio_service.validate_annotation_file(textgrid)
            tg_path, _ = await audio_service.save_file(textgrid, subdir="annotations")
            parsed_transcript = annotation_service.parse_textgrid(tg_path)

            annotation = AnnotationFile(
                meeting_id=meeting_id,
                file_type="textgrid",
                file_name=textgrid.filename or "unknown.TextGrid",
                file_path=tg_path,
                parsed_data=parsed_transcript,
            )
            db.add(annotation)

            if skip_transcription:
                context.transcript = parsed_transcript

        except ValueError as e:
            logger.warning(f"TextGrid 處理失敗：{e}")

    # 處理 RTTM
    if rttm:
        try:
            audio_service.validate_annotation_file(rttm)
            rttm_path, _ = await audio_service.save_file(rttm, subdir="annotations")
            parsed_speakers = annotation_service.parse_rttm(rttm_path)

            annotation = AnnotationFile(
                meeting_id=meeting_id,
                file_type="rttm",
                file_name=rttm.filename or "unknown.rttm",
                file_path=rttm_path,
                parsed_data=json.dumps(parsed_speakers, ensure_ascii=False),
            )
            db.add(annotation)
            context.speakers = parsed_speakers

        except ValueError as e:
            logger.warning(f"RTTM 處理失敗：{e}")

    await db.commit()

    # 若沒有有效的 context 內容，回傳 None
    if not context.transcript and not context.speakers:
        return None

    return context


@router.post("/{meeting_id}/retry", response_model=UploadResponse)
async def retry_processing(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    mode: str | None = Query(None),
) -> UploadResponse:
    """失敗後重新觸發處理（允許切換 Provider）。

    Args:
        meeting_id: 會議紀錄 ID。
        background_tasks: FastAPI 背景任務。
        db: 資料庫 Session。
        mode: 處理模式（可切換）。

    Returns:
        更新後的狀態。
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if meeting.status != MeetingStatus.FAILED:
        raise HTTPException(status_code=400, detail="僅失敗的會議可重試")

    if not meeting.file_path:
        raise HTTPException(status_code=400, detail="音檔已刪除，無法重試")

    effective_mode = mode or meeting.provider or "remote"
    processor = get_audio_processor(effective_mode)

    meeting.status = MeetingStatus.PROCESSING
    meeting.provider = effective_mode
    meeting.error_message = None
    await db.commit()

    background_tasks.add_task(process_meeting, meeting.id, processor)

    return UploadResponse(meeting_id=meeting.id, status="processing")


@router.post("/{meeting_id}/summarize", response_model=MessageResponse)
async def summarize_with_ollama(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """對已有逐字稿的會議，用 Ollama 生成摘要與 Action Items。

    Args:
        meeting_id: 會議紀錄 ID。
        db: 資料庫 Session。

    Returns:
        處理結果訊息。
    """
    if not await ollama_service.is_available():
        raise HTTPException(status_code=503, detail="Ollama 服務不可用，請確認已啟動")

    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.action_items))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="此會議沒有逐字稿，無法生成摘要")

    summary_result = await ollama_service.generate_summary(meeting.transcript)
    if not summary_result:
        raise HTTPException(status_code=500, detail="Ollama 摘要生成失敗，請稍後重試")

    meeting.summary = summary_result.get("summary", "")

    if not meeting.title and summary_result.get("suggested_title"):
        meeting.title = summary_result["suggested_title"]

    # 新增 Action Items
    for item_data in summary_result.get("action_items", []):
        action = ActionItem(
            meeting_id=meeting_id,
            description=item_data.get("description", ""),
            assignee=item_data.get("assignee"),
            due_date=item_data.get("due_date"),
        )
        db.add(action)

    await db.commit()
    return MessageResponse(detail="摘要生成完成")


@router.get("/{meeting_id}/status", response_model=MeetingStatusResponse)
async def get_meeting_status(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Meeting:
    """查詢處理狀態（供 HTMX polling）。

    Args:
        meeting_id: 會議紀錄 ID。
        db: 資料庫 Session。

    Returns:
        狀態、Provider、錯誤訊息。
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")
    return meeting


@router.get("", response_model=list[MeetingListItem])
async def list_meetings(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[Meeting]:
    """取得會議列表（時間倒序）。

    Args:
        db: 資料庫 Session。

    Returns:
        會議列表。
    """
    result = await db.execute(
        select(Meeting).order_by(Meeting.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Meeting:
    """取得完整會議資料。

    Args:
        meeting_id: 會議紀錄 ID。
        db: 資料庫 Session。

    Returns:
        完整會議資料（含 Action Items）。
    """
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.action_items))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")
    return meeting


@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    data: MeetingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Meeting:
    """編輯會議（標題、摘要、逐字稿）。

    Args:
        meeting_id: 會議紀錄 ID。
        data: 更新資料。
        db: 資料庫 Session。

    Returns:
        更新後的會議資料。
    """
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.action_items))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if data.title is not None:
        meeting.title = data.title
    if data.transcript is not None:
        meeting.transcript = data.transcript
    if data.summary is not None:
        meeting.summary = data.summary

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", response_model=MessageResponse)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """刪除會議紀錄（含音檔）。

    Args:
        meeting_id: 會議紀錄 ID。
        db: 資料庫 Session。

    Returns:
        刪除結果。
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if meeting.file_path:
        audio_service.delete_audio_file(meeting.file_path)

    await db.delete(meeting)
    await db.commit()
    return MessageResponse(detail="會議紀錄已刪除")


@router.delete("/{meeting_id}/audio", response_model=MessageResponse)
async def delete_meeting_audio(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """僅刪除音檔（保留文字紀錄）。

    Args:
        meeting_id: 會議紀錄 ID。
        db: 資料庫 Session。

    Returns:
        刪除結果。
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if not meeting.file_path:
        raise HTTPException(status_code=400, detail="音檔已刪除")

    audio_service.delete_audio_file(meeting.file_path)
    meeting.file_path = None
    await db.commit()
    return MessageResponse(detail="音檔已刪除")


# === Action Items CRUD ===


@router.post("/{meeting_id}/actions", response_model=ActionItemResponse)
async def create_action_item(
    meeting_id: str,
    data: ActionItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ActionItem:
    """新增 Action Item。

    Args:
        meeting_id: 會議紀錄 ID。
        data: Action Item 資料。
        db: 資料庫 Session。

    Returns:
        新建的 Action Item。
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    action = ActionItem(
        meeting_id=meeting_id,
        description=data.description,
        assignee=data.assignee,
        due_date=data.due_date,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.put("/{meeting_id}/actions/{action_id}", response_model=ActionItemResponse)
async def update_action_item(
    meeting_id: str,
    action_id: str,
    data: ActionItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ActionItem:
    """編輯 Action Item。

    Args:
        meeting_id: 會議紀錄 ID。
        action_id: Action Item ID。
        data: 更新資料。
        db: 資料庫 Session。

    Returns:
        更新後的 Action Item。
    """
    action = await db.get(ActionItem, action_id)
    if not action or action.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Action Item 不存在")

    if data.description is not None:
        action.description = data.description
    if data.assignee is not None:
        action.assignee = data.assignee
    if data.due_date is not None:
        action.due_date = data.due_date
    if data.is_completed is not None:
        action.is_completed = data.is_completed

    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{meeting_id}/actions/{action_id}", response_model=MessageResponse)
async def delete_action_item(
    meeting_id: str,
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    """刪除 Action Item。

    Args:
        meeting_id: 會議紀錄 ID。
        action_id: Action Item ID。
        db: 資料庫 Session。

    Returns:
        刪除結果。
    """
    action = await db.get(ActionItem, action_id)
    if not action or action.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="Action Item 不存在")

    await db.delete(action)
    await db.commit()
    return MessageResponse(detail="Action Item 已刪除")
