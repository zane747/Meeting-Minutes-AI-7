"""會議相關 REST API 路由。

==================== 學習備註 ====================
【這個檔案是什麼？】
這是「後端 API 路由」檔案 —— 定義了前端可以呼叫的所有 API 端點。
當前端用 fetch() 送出請求，就是送到這裡來處理的。

【什麼是 REST API？】
REST 是一種設計 API 的規範，用 HTTP 方法表達意圖：
  GET    → 讀取資料（例如：取得會議列表）
  POST   → 新增資料（例如：上傳新會議）
  PUT    → 更新資料（例如：編輯會議標題）
  DELETE → 刪除資料（例如：刪除會議）

【這個檔案在架構中的位置 — 三層式架構】
  前端 (templates/) → API 路由 (這個檔案) → 服務層 (services/) → 資料庫 (database.py)
  路由層只負責：接收請求 → 呼叫服務層 → 回傳結果
  業務邏輯放在 services/，資料存取放在 database.py。
  這就是考核表提到的「MVC 與三層式架構」。
================================================
"""

import json
import logging

# 【import — 引入需要的工具】
# 把其他檔案的功能「借過來用」。就像工具箱，需要什麼就拿什麼。
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
# APIRouter → 用來定義一組 API 路由（像一個資料夾，把相關的 API 放在一起）
# BackgroundTasks → 背景任務（耗時工作丟到背景跑，不讓使用者等）
# Depends → 依賴注入（自動準備好需要的東西，例如資料庫連線）
# HTTPException → HTTP 錯誤回應（例如 404 找不到、400 請求有誤）
# Query → 從 URL 的 ?key=value 取值
# UploadFile → 代表上傳的檔案

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
# SQLAlchemy 是「ORM」— 讓你用 Python 物件操作資料庫，不用寫 SQL 語法。
# select → 查詢資料（等於 SQL 的 SELECT）
# AsyncSession → 非同步的資料庫連線
# selectinload → 一次把關聯的資料也讀出來（避免 N+1 查詢問題）

from app.database import get_db
# get_db → 取得資料庫連線的函式（搭配 Depends 使用）

from app.dependencies import get_audio_processor
from app.models.database_models import (
    ActionItem,
    AnnotationFile,
    Meeting,
    MeetingStatus,
    Speaker,
    Topic,
    Utterance,
)
# 這些是「資料模型」— 定義了資料庫裡每張表長什麼樣子。
# Meeting = 會議表, Speaker = 說話者表, etc.

from app.models.schemas import (
    ActionItemCreate,
    ActionItemResponse,
    ActionItemUpdate,
    MeetingListItem,
    MeetingResponse,
    MeetingStatusResponse,
    MeetingUpdate,
    MessageResponse,
    SpeakerResponse,
    SpeakerUpdateRequest,
    TopicResponse,
    UploadResponse,
    UtteranceResponse,
)
# 這些是「Schema（結構定義）」— 用 Pydantic 定義 API 的輸入/輸出格式。
# xxxResponse → 定義回傳給前端的 JSON 長什麼樣
# xxxCreate/xxxUpdate → 定義前端傳過來的資料格式
# 這就是「規格驅動開發」的一部分：先定義好資料的形狀，再寫邏輯。

from app.config import settings
from app.services import annotation_service, audio_service, ollama_service
from app.services.device_manager import DeviceManager
from app.services.meeting_processor import process_meeting
from app.services.providers.base import ProcessingContext

logger = logging.getLogger(__name__)
# logger 用來記錄程式運行的日誌（像寫日記），方便除錯。

# 【APIRouter — 路由分組】
# prefix="/api/meetings" → 這個檔案裡所有 API 的路徑都會自動加上 /api/meetings
# 例如：@router.post("/upload-and-process") 實際路徑是 /api/meetings/upload-and-process
# tags=["meetings"] → 在 API 文件（Swagger UI）裡分類用
router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def _parse_time_to_seconds(time_str: str) -> float | None:
    """將 MM:SS 或 HH:MM:SS 格式轉為秒數。"""
    if not time_str:
        return None
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, IndexError):
        pass
    return None


# ==================== 核心 API：上傳並處理（資料傳遞的終點！） ====================
# 這是前端 fetch() 送出請求後，第一個接手的後端函式。
# ============================================================================
@router.post("/upload-and-process", response_model=UploadResponse)
# @router.post(...) 是「裝飾器 (Decorator)」
# 意思是：「當有人用 POST 方法請求 /api/meetings/upload-and-process 時，執行下面這個函式」
# response_model=UploadResponse → 告訴 FastAPI「回傳的 JSON 要符合 UploadResponse 的格式」
async def upload_and_process(
    # 【參數 — FastAPI 自動從請求中取出資料】
    # FastAPI 看到參數的「型別」就知道去哪裡找資料：
    #
    # UploadFile → 從 FormData 的 body 裡找檔案
    file: UploadFile,                       # ← 對應前端 formData.append('file', file)
    background_tasks: BackgroundTasks,      # ← FastAPI 自動注入，用來安排背景任務
    db: AsyncSession = Depends(get_db),     # ← 依賴注入：自動取得資料庫連線
    # 【依賴注入 (Dependency Injection) 白話解釋】
    # Depends(get_db) 的意思是：
    #   「在呼叫這個函式之前，先執行 get_db() 拿到資料庫連線，
    #    然後把結果塞進 db 這個參數。」
    # 好處：你不用手動建立/關閉資料庫連線，FastAPI 幫你管。
    textgrid: UploadFile | None = None,     # ← 選填檔案（| None = None 表示可以不傳）
    rttm: UploadFile | None = None,         # ← 選填檔案
    title: str | None = None,              # ← 從 FormData 取文字（對應 formData.append('title', ...))
    mode: str | None = Query(None),        # ← 從 URL ?mode=xxx 取值（Query 明確指定來源）
    skip_transcription: bool = False,      # ← 從 URL query string 取，自動轉成 bool
    duration: float = 0.0,                 # ← 從 FormData 取，自動轉成 float
    enable_diarization: bool = False,      # ← 從 URL query string 取
    num_speakers: int | None = None,       # ← 從 URL query string 取
) -> UploadResponse:
    """上傳音檔（+ TextGrid/RTTM 選填）+ 自動觸發 AI 處理。"""

    # 【第 1 步：後端驗證】
    # 前端已經驗證過一次了，但後端一定要再驗一次！
    # 因為有人可能跳過前端（例如用 Postman 或 curl 直接呼叫 API）。
    try:
        audio_service.validate_audio_file(file)
    except ValueError as e:
        # 【HTTPException — 回傳錯誤給前端】
        # status_code=400 → Bad Request（使用者的請求有問題）
        # detail=... → 錯誤訊息，前端會從 resp.json().detail 讀到
        raise HTTPException(status_code=400, detail=str(e))

    # 【第 2 步：儲存檔案到磁碟】
    # 上傳的檔案先存到伺服器的 uploads/ 資料夾
    try:
        file_path, file_size = await audio_service.save_file(file)
        # await → 因為存檔是 I/O 操作（寫入磁碟），需要等待
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 後端計算時長（若前端未提供，後端自己算，雙重保險）
    if duration <= 0:
        duration = audio_service.get_duration(file_path)

    # 【第 3 步：決定用哪個 AI 服務處理】
    # mode="remote" → 用 Gemini API（雲端）
    # mode="local"  → 用本地的 Whisper + Ollama
    effective_mode = mode or "remote"  # 沒指定就預設用 remote
    processor = get_audio_processor(effective_mode)

    # 【第 4 步：建立資料庫紀錄】
    # 用 ORM（SQLAlchemy）建立一筆新的 Meeting 紀錄。
    # 不用寫 SQL，直接建立 Python 物件，SQLAlchemy 會幫你轉成：
    # INSERT INTO meetings (title, file_name, ...) VALUES ('xxx', 'yyy', ...)
    meeting = Meeting(
        title=title,                        # 使用者填的標題（可能是 None）
        file_name=file.filename or "unknown",
        file_path=file_path,                # 檔案存在磁碟的路徑
        file_size=file_size,
        duration=duration,
        status=MeetingStatus.PROCESSING,    # 狀態設為「處理中」
        provider=effective_mode,
    )
    db.add(meeting)         # 加入資料庫 session（還沒真正寫入）
    await db.commit()       # 真正寫入資料庫（像按下「儲存」）
    await db.refresh(meeting)  # 重新讀取，拿到資料庫自動生成的 id

    # 【第 5 步：處理附件】
    context = await _process_annotations(
        meeting.id, textgrid, rttm, skip_transcription, db
    )

    # 注入 diarization 參數
    if enable_diarization:
        if context is None:
            context = ProcessingContext()
        context.diarization_enabled = True
        context.num_speakers = num_speakers if num_speakers and num_speakers > 0 else None

    # 【第 6 步：送入背景任務】
    # AI 處理音檔很慢（可能要幾分鐘），不能讓使用者一直等。
    # background_tasks.add_task() 會在「回應已經送出後」才在背景執行。
    # 使用者會先收到回應，然後前端用 polling 去查詢處理進度。
    background_tasks.add_task(process_meeting, meeting.id, processor, context)

    # 【第 7 步：回傳 JSON 給前端】
    # FastAPI 會自動把 UploadResponse 物件轉成 JSON：
    # {"meeting_id": "abc-123", "status": "processing"}
    # 前端的 resp.json() 就會收到這個。
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
    meeting.progress = 0
    meeting.progress_stage = None
    await db.commit()

    background_tasks.add_task(process_meeting, meeting.id, processor)

    return UploadResponse(meeting_id=meeting.id, status="processing")


@router.post("/{meeting_id}/summarize", response_model=MessageResponse)
async def summarize_with_ollama(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
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

    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if not meeting.transcript:
        raise HTTPException(status_code=400, detail="此會議沒有逐字稿，無法生成摘要")

    # 並行防護：避免同一會議被重複生成摘要
    if meeting.progress_stage == "摘要重新生成中...":
        raise HTTPException(status_code=409, detail="此會議正在重新生成摘要，請稍後")

    meeting.progress_stage = "摘要重新生成中..."
    await db.commit()

    try:
        # 先生成新摘要（舊資料尚未刪除，失敗時不影響既有資料）
        gpu_mode = settings.OLLAMA_GPU.lower()
        if gpu_mode in ("auto", "true"):
            async with DeviceManager.get_gpu_lock():
                summary_result = await ollama_service.generate_summary(meeting.transcript)
        else:
            summary_result = await ollama_service.generate_summary(meeting.transcript)

        if not summary_result:
            meeting.progress_stage = None
            await db.commit()
            raise HTTPException(status_code=500, detail="Ollama 摘要生成失敗，請稍後重試")

        # 成功後才刪除舊資料（避免失敗時丟失既有摘要）
        result = await db.execute(
            select(Meeting)
            .options(selectinload(Meeting.action_items), selectinload(Meeting.topics))
            .where(Meeting.id == meeting_id)
        )
        meeting = result.scalar_one()

        for item in list(meeting.action_items):
            await db.delete(item)
        for topic in list(meeting.topics):
            await db.delete(topic)

        # 寫入新結果
        meeting.summary = summary_result.get("summary", "")

        if summary_result.get("suggested_title"):
            meeting.title = summary_result["suggested_title"]

        for item_data in summary_result.get("action_items", []):
            action = ActionItem(
                meeting_id=meeting_id,
                description=item_data.get("description", ""),
                assignee=item_data.get("assignee"),
                due_date=item_data.get("due_date"),
            )
            db.add(action)

        # 儲存 Semantic Analysis（Topics）
        sa = summary_result.get("semantic_analysis")
        if sa:
            for idx, topic_data in enumerate(sa.get("topics", [])):
                start_time = _parse_time_to_seconds(topic_data.get("start_time", ""))
                end_time = _parse_time_to_seconds(topic_data.get("end_time", ""))
                topic = Topic(
                    meeting_id=meeting_id,
                    title=topic_data.get("title", ""),
                    start_time=start_time,
                    end_time=end_time,
                    order_index=idx,
                )
                db.add(topic)

        meeting.progress_stage = None
        await db.commit()
        return MessageResponse(detail="摘要生成完成")

    except HTTPException:
        raise
    except Exception:
        meeting.progress_stage = None
        await db.commit()
        raise


# 【GET API — 讀取資料】
# @router.get → 用 GET 方法（瀏覽器輸入網址就是 GET）
# /{meeting_id} → URL 路徑參數，例如 /api/meetings/abc-123/status
#   meeting_id 會自動被填入 "abc-123"
@router.get("/{meeting_id}/status", response_model=MeetingStatusResponse)
async def get_meeting_status(
    meeting_id: str,  # ← 從 URL 路徑取出，例如 /status 前面的 abc-123
    db: AsyncSession = Depends(get_db),
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


# 【列表 API — 回傳多筆資料】
# 路徑是 "" → 加上 prefix 就是 /api/meetings（沒有額外路徑）
# response_model=list[MeetingListItem] → 回傳的是「MeetingListItem 的陣列」
@router.get("", response_model=list[MeetingListItem])
async def list_meetings(
    db: AsyncSession = Depends(get_db),
) -> list[Meeting]:
    """取得會議列表（時間倒序）。"""
    # 【ORM 查詢 — 等於 SQL: SELECT * FROM meetings ORDER BY created_at DESC】
    # select(Meeting) → 查 meetings 表
    # .order_by(Meeting.created_at.desc()) → 按建立時間倒序（最新的在前面）
    result = await db.execute(
        select(Meeting).order_by(Meeting.created_at.desc())
    )
    # scalars().all() → 取出所有結果，變成 Python list
    return list(result.scalars().all())


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
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


# 【PUT API — 更新資料】
# PUT 代表「更新既有的資料」
# data: MeetingUpdate → 這次前端傳的是 JSON body（不是 FormData）
#   前端會用 fetch(url, { method: 'PUT', body: JSON.stringify({title: '新標題'}) })
#   FastAPI 看到參數是 Pydantic model（MeetingUpdate），就知道要從 JSON body 取值
@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: str,
    data: MeetingUpdate,  # ← 從 JSON body 自動解析（跟 UploadFile 從 FormData 取不同！）
    db: AsyncSession = Depends(get_db),
) -> Meeting:
    """編輯會議（標題、摘要、逐字稿）。"""
    # 查詢資料庫，找到要更新的會議
    result = await db.execute(
        select(Meeting)
        .options(selectinload(Meeting.action_items)) # 同時載入關聯的 action_items
        .where(Meeting.id == meeting_id)             # WHERE id = 'xxx'
    )
    meeting = result.scalar_one_or_none()  # 取一筆，沒有就回傳 None
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")
        # 404 = Not Found（找不到這筆資料）

    # 【部分更新 (Partial Update)】
    # 只更新前端有傳的欄位（is not None 的才更新）
    # 這是 PUT/PATCH API 的常見模式
    if data.title is not None:
        meeting.title = data.title
    if data.transcript is not None:
        meeting.transcript = data.transcript
    if data.summary is not None:
        meeting.summary = data.summary

    await db.commit()          # 寫入資料庫
    await db.refresh(meeting)  # 重新讀取最新資料
    return meeting             # 回傳更新後的完整資料


# 【DELETE API — 刪除資料】
# 注意刪除通常要做兩件事：
#   1. 刪除磁碟上的檔案（音檔）
#   2. 刪除資料庫中的紀錄
# 順序很重要：先刪檔案再刪紀錄。如果反過來，紀錄刪了但檔案刪除失敗，
# 就會變成「孤兒檔案」佔用磁碟空間。
@router.delete("/{meeting_id}", response_model=MessageResponse)
async def delete_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """刪除會議紀錄（含音檔）。"""
    meeting = await db.get(Meeting, meeting_id)
    # db.get() 是用主鍵（Primary Key）查詢的快捷方式
    # 等於 SELECT * FROM meetings WHERE id = 'xxx'
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    if meeting.file_path:
        audio_service.delete_audio_file(meeting.file_path)  # 1. 先刪磁碟上的檔案

    await db.delete(meeting)  # 2. 再刪資料庫紀錄
    await db.commit()
    return MessageResponse(detail="會議紀錄已刪除")


@router.delete("/{meeting_id}/audio", response_model=MessageResponse)
async def delete_meeting_audio(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
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


# === Speaker & Utterance APIs ===


@router.get("/{meeting_id}/speakers", response_model=list[SpeakerResponse])
async def get_speakers(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Speaker]:
    """取得該會議所有說話者。"""
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    result = await db.execute(
        select(Speaker).where(Speaker.meeting_id == meeting_id)
    )
    return list(result.scalars().all())


@router.put("/{meeting_id}/speakers/{speaker_id}", response_model=SpeakerResponse)
async def update_speaker(
    meeting_id: str,
    speaker_id: str,
    data: SpeakerUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> Speaker:
    """更新說話者名稱或顏色。"""
    speaker = await db.get(Speaker, speaker_id)
    if not speaker or speaker.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="說話者不存在")

    if data.display_name is not None:
        speaker.display_name = data.display_name
    if data.color is not None:
        speaker.color = data.color

    await db.commit()
    await db.refresh(speaker)
    return speaker


@router.get("/{meeting_id}/utterances", response_model=list[UtteranceResponse])
async def get_utterances(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    speaker_id: str | None = Query(None),
) -> list[dict]:
    """取得發言段落（可按說話者篩選）。"""
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    query = (
        select(Utterance, Speaker)
        .outerjoin(Speaker, Utterance.speaker_id == Speaker.id)
        .where(Utterance.meeting_id == meeting_id)
        .order_by(Utterance.order_index)
    )

    if speaker_id:
        query = query.where(Utterance.speaker_id == speaker_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": utt.id,
            "meeting_id": utt.meeting_id,
            "speaker_id": utt.speaker_id,
            "speaker_label": spk.label if spk else None,
            "speaker_display_name": spk.display_name if spk else None,
            "speaker_color": spk.color if spk else None,
            "start_time": utt.start_time,
            "end_time": utt.end_time,
            "text": utt.text,
            "intent_tag": utt.intent_tag,
            "order_index": utt.order_index,
        }
        for utt, spk in rows
    ]


@router.get("/{meeting_id}/topics", response_model=list[TopicResponse])
async def get_topics(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Topic]:
    """取得該會議的主題段落列表。"""
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="會議紀錄不存在")

    result = await db.execute(
        select(Topic)
        .where(Topic.meeting_id == meeting_id)
        .order_by(Topic.order_index)
    )
    return list(result.scalars().all())


# === Action Items CRUD ===


@router.post("/{meeting_id}/actions", response_model=ActionItemResponse)
async def create_action_item(
    meeting_id: str,
    data: ActionItemCreate,
    db: AsyncSession = Depends(get_db),
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
