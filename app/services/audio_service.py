"""音檔上傳、驗證與管理服務。"""

import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac"}
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
}

ALLOWED_ANNOTATION_EXTENSIONS = {".textgrid", ".rttm"}


def validate_audio_file(file: UploadFile) -> None:
    """驗證上傳音檔的格式。

    Args:
        file: FastAPI UploadFile 物件。

    Raises:
        ValueError: 當檔案格式不支援時。
    """
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"不支援的音檔格式：{ext}。"
                f"僅支援 {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
            )

    if file.content_type and file.content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise ValueError(f"不支援的音檔類型：{file.content_type}")


def validate_annotation_file(file: UploadFile) -> str:
    """驗證上傳標註檔的格式。

    Args:
        file: FastAPI UploadFile 物件。

    Returns:
        標註檔類型（"textgrid" 或 "rttm"）。

    Raises:
        ValueError: 當檔案格式不支援時。
    """
    if not file.filename:
        raise ValueError("標註檔缺少檔案名稱")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_ANNOTATION_EXTENSIONS:
        raise ValueError(
            f"不支援的標註檔格式：{ext}。"
            f"僅支援 {', '.join(ALLOWED_ANNOTATION_EXTENSIONS)}"
        )

    return "textgrid" if ext == ".textgrid" else "rttm"


# 保留舊名稱作為別名，向後相容
validate_file = validate_audio_file


async def save_file(file: UploadFile, subdir: str = "") -> tuple[str, int]:
    """儲存上傳的檔案至 uploads 目錄。

    使用分塊讀取避免大檔案一次性佔用記憶體。
    超過大小限制時立即中斷讀取。

    Args:
        file: FastAPI UploadFile 物件。
        subdir: 子目錄名稱（例如 "annotations"）。

    Returns:
        (儲存路徑, 檔案大小 bytes) 的 tuple。

    Raises:
        ValueError: 當檔案超過大小限制時。
    """
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    unique_name = f"{uuid.uuid4()}{ext}"

    save_dir = Path(settings.UPLOAD_DIR)
    if subdir:
        save_dir = save_dir / subdir
        save_dir.mkdir(parents=True, exist_ok=True)

    save_path = save_dir / unique_name
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

    logger.info(f"檔案已儲存：{save_path}（{file_size} bytes）")

    return str(save_path), file_size


def delete_file(file_path: str) -> bool:
    """刪除檔案。

    Args:
        file_path: 檔案路徑。

    Returns:
        True 表示刪除成功，False 表示檔案不存在。
    """
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info(f"檔案已刪除：{file_path}")
        return True
    logger.warning(f"檔案不存在：{file_path}")
    return False


# 保留舊名稱作為別名
delete_audio_file = delete_file


def get_duration(file_path: str) -> float:
    """取得音檔時長（秒）。

    優先使用 ffprobe（無需 audioop），fallback 至 pydub。

    Args:
        file_path: 音檔路徑。

    Returns:
        音檔時長（秒）。
    """
    # 優先使用 ffprobe（不依賴 audioop，相容 Python 3.13+）
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass

    # Fallback: pydub（需要 audioop）
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(file_path)
        return len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"無法取得音檔時長：{e}")
        return 0.0
