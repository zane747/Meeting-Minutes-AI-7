"""音檔上傳、驗證與管理服務。"""

import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".mp3", ".wav"}
ALLOWED_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/wave"}


def validate_file(file: UploadFile) -> None:
    """驗證上傳檔案的格式與大小。

    Args:
        file: FastAPI UploadFile 物件。

    Raises:
        ValueError: 當檔案格式不支援或超過大小限制時。
    """
    # 驗證副檔名
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"不支援的檔案格式：{ext}。僅支援 {', '.join(ALLOWED_EXTENSIONS)}"
            )

    # 驗證 MIME type
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"不支援的檔案類型：{file.content_type}")


async def save_file(file: UploadFile) -> tuple[str, int]:
    """儲存上傳的音檔至 uploads 目錄。

    使用分塊讀取避免大檔案一次性佔用記憶體。
    超過大小限制時立即中斷讀取。

    Args:
        file: FastAPI UploadFile 物件。

    Returns:
        (儲存路徑, 檔案大小 bytes) 的 tuple。

    Raises:
        ValueError: 當檔案超過大小限制時。
    """
    ext = Path(file.filename).suffix.lower() if file.filename else ".mp3"
    unique_name = f"{uuid.uuid4()}{ext}"
    save_path = Path(settings.UPLOAD_DIR) / unique_name
    max_bytes = settings.max_file_size_bytes
    chunk_size = 1024 * 1024  # 1MB chunks

    file_size = 0
    with open(save_path, "wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > max_bytes:
                f.close()
                save_path.unlink(missing_ok=True)
                raise ValueError(
                    f"檔案大小超過上限 {settings.MAX_FILE_SIZE_MB}MB"
                )
            f.write(chunk)

    logger.info(f"音檔已儲存：{save_path}（{file_size} bytes）")

    return str(save_path), file_size


def delete_audio_file(file_path: str) -> bool:
    """刪除音檔。

    Args:
        file_path: 音檔路徑。

    Returns:
        True 表示刪除成功，False 表示檔案不存在。
    """
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info(f"音檔已刪除：{file_path}")
        return True
    logger.warning(f"音檔不存在：{file_path}")
    return False


def get_duration(file_path: str) -> float:
    """使用 pydub 取得音檔時長（秒）。

    Args:
        file_path: 音檔路徑。

    Returns:
        音檔時長（秒）。
    """
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"無法取得音檔時長：{e}")
        return 0.0
