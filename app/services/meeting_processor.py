"""MeetingProcessor：協調層，呼叫 Provider 並儲存結果至 DB。

在 BackgroundTask 中執行，自行建立獨立的資料庫 Session。
負責組裝 ProcessingContext（TextGrid/RTTM）並傳入 Provider。
GPU 推論使用 DeviceManager.get_gpu_lock() 確保同一時間只有一個任務佔用 GPU。
"""

import logging

from app.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ProcessingError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.database import async_session
from app.models.database_models import (
    ActionItem,
    Meeting,
    MeetingStatus,
    Speaker,
    Topic,
    Utterance,
)
from app.services.device_manager import DeviceManager
from app.services.diarization_service import diarization_service
from app.services.providers.base import AudioProcessor, ProcessingContext

logger = logging.getLogger(__name__)


async def _update_progress(
    meeting_id: str, progress: int, stage: str, db=None
) -> None:
    """更新會議處理進度。"""
    if db:
        meeting = await db.get(Meeting, meeting_id)
        if meeting:
            meeting.progress = progress
            meeting.progress_stage = stage
            await db.commit()
            logger.info(f"Meeting {meeting_id}: 進度 {progress}% - {stage}")


def _parse_time_str(time_str: str) -> float | None:
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


async def process_meeting(
    meeting_id: str,
    processor: AudioProcessor,
    context: ProcessingContext | None = None,
) -> None:
    """執行 AI 處理並儲存結果至資料庫。

    此函式在 BackgroundTask 中執行，自行建立獨立的 DB Session。

    Args:
        meeting_id: 會議紀錄 ID。
        processor: AudioProcessor 實例。
        context: 標註檔上下文（TextGrid/RTTM），可選。
    """
    async with async_session() as db:
        meeting = await db.get(Meeting, meeting_id)
        if not meeting:
            logger.error(f"Meeting 不存在：{meeting_id}")
            return

        try:
            # 健康檢查
            await _update_progress(meeting_id, 5, "檢查服務連線中...", db)
            if not await processor.health_check():
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = (
                    f"{processor.get_provider_name()} 無法連線"
                )
                await db.commit()
                return

            await _update_progress(meeting_id, 10, "排隊等待 GPU 資源...", db)

            # GPU 推論排隊：Diarization + AI 處理 共用 DeviceManager 的全域 lock
            async with DeviceManager.get_gpu_lock():
                logger.info(
                    "Meeting %s: 取得 GPU lock，開始處理", meeting_id
                )

                # Diarization 步驟（可選）
                diarization_warning = None
                if context and context.diarization_enabled:
                    await _update_progress(meeting_id, 15, "說話者辨識中...", db)
                    if context.speakers:
                        # RTTM 優先：使用者已上傳 RTTM，跳過 pyannote
                        logger.info(
                            f"Meeting {meeting_id}: 使用者提供 RTTM，跳過自動 diarization"
                        )
                    elif diarization_service.is_available():
                        num = context.num_speakers if context.num_speakers else None
                        segments = await diarization_service.diarize(
                            meeting.file_path, num_speakers=num
                        )
                        if segments:
                            context.speakers = [
                                {
                                    "speaker": s.speaker,
                                    "start": s.start,
                                    "end": s.end,
                                }
                                for s in segments
                            ]
                            logger.info(
                                f"Meeting {meeting_id}: diarization 完成，"
                                f"{len(set(s.speaker for s in segments))} 位說話者"
                            )
                        else:
                            diarization_warning = "說話者辨識執行失敗，已略過"
                            logger.warning(
                                f"Meeting {meeting_id}: diarization 回傳空結果"
                            )
                    else:
                        diarization_warning = (
                            "說話者辨識服務不可用"
                            "（請確認 pyannote 安裝與 HF_TOKEN 設定）"
                        )
                        logger.warning(
                            f"Meeting {meeting_id}: diarization 服務不可用"
                        )

                # 執行 AI 處理（傳入 context）
                await _update_progress(meeting_id, 30, "AI 轉錄與分析中...", db)
                logger.info(
                    f"開始處理 Meeting {meeting_id}"
                    f"（Provider: {processor.get_provider_name()}）"
                )
                result = await processor.process(meeting.file_path, context)

            logger.info("Meeting %s: 釋放 GPU lock", meeting_id)

            # 將 diarization warning 附加到 result
            if diarization_warning:
                result.diarization_warning = diarization_warning

            # Ollama 摘要（GPU lock 外執行，避免 CPU 模式被 lock 擋住）
            if settings.OLLAMA_ENABLED and result.transcript and not result.summary:
                await _update_progress(meeting_id, 60, "生成摘要中...", db)
                from app.services import ollama_service

                async def _progress_cb(pct: int, stage: str) -> None:
                    await _update_progress(meeting_id, pct, stage, db)

                # auto/true 模式需要 GPU lock 保護
                gpu_mode = settings.OLLAMA_GPU.lower()
                if gpu_mode in ("auto", "true"):
                    async with DeviceManager.get_gpu_lock():
                        summary_result = await ollama_service.generate_summary(
                            result.transcript,
                            progress_callback=_progress_cb,
                        )
                else:
                    summary_result = await ollama_service.generate_summary(
                        result.transcript,
                        progress_callback=_progress_cb,
                    )

                if summary_result:
                    result.summary = summary_result.get("summary", "")
                    result.suggested_title = summary_result.get("suggested_title")
                    result.action_items = summary_result.get("action_items", [])
                    result.semantic_analysis = summary_result.get("semantic_analysis")
                    logger.info("Meeting %s: Ollama 摘要生成完成", meeting_id)

            await _update_progress(meeting_id, 80, "儲存分析結果中...", db)

            # 初始化（供後續 semantic_analysis 使用）
            speaker_map = {}
            db_utterances_list = []

            # 儲存結果
            meeting.transcript = result.transcript
            meeting.summary = result.summary
            meeting.status = MeetingStatus.COMPLETED

            # 若使用者未填標題，使用 AI 建議標題
            if not meeting.title and result.suggested_title:
                meeting.title = result.suggested_title

            # 儲存 Action Items
            for item in result.action_items:
                action = ActionItem(
                    meeting_id=meeting_id,
                    description=item.get("description", ""),
                    assignee=item.get("assignee"),
                    due_date=item.get("due_date"),
                )
                db.add(action)

            # 儲存 Speakers 與 Utterances（若有 diarization 資料）
            if context and context.speakers and result.transcript:
                speaker_map = {}
                unique_labels = sorted(
                    set(s["speaker"] for s in context.speakers)
                )
                for i, label in enumerate(unique_labels):
                    speaker = Speaker(
                        meeting_id=meeting_id,
                        label=label,
                        color=diarization_service.get_speaker_color(i),
                    )
                    db.add(speaker)
                    speaker_map[label] = speaker

                # 合併 transcript 與 diarization → utterances
                from app.services.diarization_service import SpeakerSegment

                segments = [
                    SpeakerSegment(
                        speaker=s["speaker"],
                        start=s["start"],
                        end=s["end"],
                    )
                    for s in context.speakers
                ]
                merged = diarization_service.merge_with_transcript(
                    segments, result.transcript
                )
                for utt in merged:
                    spk = speaker_map.get(utt.speaker)
                    utterance = Utterance(
                        meeting_id=meeting_id,
                        speaker_id=spk.id if spk else None,
                        start_time=utt.start_time,
                        end_time=utt.end_time,
                        text=utt.text,
                        order_index=utt.order_index,
                    )
                    db.add(utterance)

                logger.info(
                    f"Meeting {meeting_id}: 儲存 {len(unique_labels)} 位說話者，"
                    f"{len(merged)} 段發言"
                )

            # 儲存 Semantic Analysis（若有）
            if result.semantic_analysis:
                sa = result.semantic_analysis

                # 儲存 Topics
                for idx, topic_data in enumerate(sa.get("topics", [])):
                    start_time = _parse_time_str(topic_data.get("start_time", ""))
                    end_time = _parse_time_str(topic_data.get("end_time", ""))
                    speakers_inv = ", ".join(
                        topic_data.get("speakers_involved", [])
                    ) or None

                    topic = Topic(
                        meeting_id=meeting_id,
                        title=topic_data.get("title", ""),
                        start_time=start_time,
                        end_time=end_time,
                        order_index=idx,
                        speakers_involved=speakers_inv,
                    )
                    db.add(topic)

                # 更新 Speaker key_points / stance（若有 speaker_summaries）
                speaker_summaries = sa.get("speaker_summaries", {})
                if speaker_summaries and speaker_map:
                    for label, summary_data in speaker_summaries.items():
                        if label in speaker_map:
                            spk = speaker_map[label]
                            spk.key_points = summary_data.get("key_points", "")
                            spk.stance = summary_data.get("stance", "")

                # 更新 Utterance intent_tag（若有 utterance_intents）
                utterance_intents = sa.get("utterance_intents", [])
                if utterance_intents:
                    intent_map = {
                        item["utterance_index"]: item["intent"]
                        for item in utterance_intents
                        if "utterance_index" in item and "intent" in item
                    }
                    if intent_map:
                        from sqlalchemy import select
                        utt_result = await db.execute(
                            select(Utterance)
                            .where(Utterance.meeting_id == meeting_id)
                            .order_by(Utterance.order_index)
                        )
                        for utt in utt_result.scalars().all():
                            if utt.order_index in intent_map:
                                utt.intent_tag = intent_map[utt.order_index]

                logger.info(
                    f"Meeting {meeting_id}: 儲存語意分析"
                    f"（{len(sa.get('topics', []))} 主題）"
                )

            meeting.progress = 100
            meeting.progress_stage = "處理完成"
            meeting.error_message = None
            await db.commit()
            logger.info(f"Meeting {meeting_id} 處理完成")

        except RateLimitError as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            await db.commit()
            logger.warning(f"Meeting {meeting_id} 頻率受限：{e}")

        except AuthenticationError as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            await db.commit()
            logger.error(f"Meeting {meeting_id} 認證失敗：{e}")

        except ProviderUnavailableError as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            await db.commit()
            logger.error(f"Meeting {meeting_id} Provider 不可用：{e}")

        except ProcessingError as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = str(e)
            await db.commit()
            logger.error(f"Meeting {meeting_id} 處理失敗：{e}")

        except Exception as e:
            meeting.status = MeetingStatus.FAILED
            meeting.error_message = "處理失敗，請重試或切換處理模式"
            await db.commit()
            logger.exception(f"Meeting {meeting_id} 未預期的錯誤：{e}")
