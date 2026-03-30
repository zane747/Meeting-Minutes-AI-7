"""MeetingProcessor：協調層，呼叫 Provider 並儲存結果至 DB。

在 BackgroundTask 中執行，自行建立獨立的資料庫 Session。
負責組裝 ProcessingContext（TextGrid/RTTM）並傳入 Provider。
"""

import logging

from app.core.exceptions import (
    AuthenticationError,
    ProcessingError,
    ProviderUnavailableError,
    RateLimitError,
)
from app.database import async_session
from app.models.database_models import ActionItem, Meeting, MeetingStatus
from app.services.providers.base import AudioProcessor, ProcessingContext

logger = logging.getLogger(__name__)


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
            # 步驟 1：健康檢查
            meeting.progress_step = "health_check"
            await db.commit()

            if not await processor.health_check():
                meeting.status = MeetingStatus.FAILED
                meeting.error_message = (
                    f"{processor.get_provider_name()} 無法連線"
                )
                meeting.progress_step = None
                await db.commit()
                return

            # 步驟 2：語音轉錄
            meeting.progress_step = "transcribing"
            await db.commit()

            logger.info(
                f"開始處理 Meeting {meeting_id}"
                f"（Provider: {processor.get_provider_name()}）"
            )
            result = await processor.process(meeting.file_path, context)

            # 步驟 3：儲存結果
            meeting.progress_step = "saving"
            await db.commit()

            meeting.transcript = result.transcript
            meeting.summary = result.summary

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

            meeting.status = MeetingStatus.COMPLETED
            meeting.error_message = None
            meeting.progress_step = None
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
