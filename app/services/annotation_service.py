"""TextGrid / RTTM 標註檔解析服務。

獨立 Service，負責解析標註檔並產出結構化資料。
與 Provider（策略模式）完全解耦。
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_textgrid(file_path: str) -> str:
    """解析 Praat TextGrid 檔案，產出帶時間戳記的逐字稿。

    支援 normal（長格式）與 short（短格式）TextGrid。
    解析所有 IntervalTier 中的非空 interval。

    Args:
        file_path: TextGrid 檔案路徑。

    Returns:
        段落式時間戳記逐字稿文字。

    Raises:
        ValueError: 當檔案格式無法解析時。
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    intervals = _parse_textgrid_intervals(content)
    if not intervals:
        raise ValueError("TextGrid 檔案中未找到有效的標註內容")

    lines = []
    for interval in intervals:
        start = _format_time(interval["start"])
        end = _format_time(interval["end"])
        text = interval["text"].strip()
        if text:
            lines.append(f"[{start} - {end}] {text}")

    transcript = "\n".join(lines)
    logger.info(f"TextGrid 解析完成：{len(intervals)} 個 intervals")
    return transcript


def _parse_textgrid_intervals(content: str) -> list[dict]:
    """從 TextGrid 內容中提取所有 interval。

    Args:
        content: TextGrid 檔案內容。

    Returns:
        interval 列表，每項包含 start、end、text。
    """
    intervals = []

    # Normal format: intervals [n]:
    #     xmin = 0.0
    #     xmax = 1.5
    #     text = "hello"
    pattern_normal = re.compile(
        r'xmin\s*=\s*([\d.]+)\s*\n\s*xmax\s*=\s*([\d.]+)\s*\n\s*text\s*=\s*"(.*?)"',
        re.DOTALL,
    )
    matches = pattern_normal.findall(content)
    if matches:
        for xmin, xmax, text in matches:
            if text.strip():
                intervals.append({
                    "start": float(xmin),
                    "end": float(xmax),
                    "text": text.strip(),
                })
        return intervals

    # Short format: lines of (xmin, xmax, "text")
    lines = content.strip().split("\n")
    i = 0
    while i < len(lines) - 2:
        try:
            xmin = float(lines[i].strip())
            xmax = float(lines[i + 1].strip())
            text = lines[i + 2].strip().strip('"')
            if text:
                intervals.append({"start": xmin, "end": xmax, "text": text})
            i += 3
        except (ValueError, IndexError):
            i += 1

    return intervals


def parse_rttm(file_path: str) -> list[dict]:
    """解析 RTTM（Rich Transcription Time Marked）檔案。

    RTTM 格式：每行一筆記錄
    SPEAKER <file> <channel> <start> <duration> <NA> <NA> <speaker> <NA> <NA>

    Args:
        file_path: RTTM 檔案路徑。

    Returns:
        說話者片段列表，每項包含 speaker、start、end。

    Raises:
        ValueError: 當檔案格式無法解析時。
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    speakers = []
    for line_num, line in enumerate(content.strip().split("\n"), 1):
        line = line.strip()
        if not line or line.startswith(";"):
            continue

        parts = line.split()
        if len(parts) < 8:
            logger.warning(f"RTTM 第 {line_num} 行格式異常，跳過：{line}")
            continue

        try:
            start = float(parts[3])
            duration = float(parts[4])
            speaker = parts[7]
            speakers.append({
                "speaker": speaker,
                "start": start,
                "end": start + duration,
            })
        except (ValueError, IndexError) as e:
            logger.warning(f"RTTM 第 {line_num} 行解析失敗：{e}")

    if not speakers:
        raise ValueError("RTTM 檔案中未找到有效的說話者片段")

    # 依 start 時間排序
    speakers.sort(key=lambda x: x["start"])
    logger.info(f"RTTM 解析完成：{len(speakers)} 個說話者片段")
    return speakers


def merge_transcript_with_speakers(
    transcript: str, speakers: list[dict]
) -> str:
    """將說話者角色標籤合併至逐字稿。

    根據 RTTM 說話者片段的時間軸，為逐字稿中的每個段落標上
    [Speaker_X] 標籤。

    Args:
        transcript: 段落式時間戳記逐字稿。
        speakers: RTTM 解析的說話者片段列表。

    Returns:
        帶有角色標籤的逐字稿。
    """
    if not speakers:
        return transcript

    lines = transcript.split("\n")
    result = []

    for line in lines:
        # 解析 [MM:SS - MM:SS] 格式
        match = re.match(r"\[(\d+:\d+)\s*-\s*(\d+:\d+)\]\s*(.*)", line)
        if not match:
            result.append(line)
            continue

        start_str, end_str, text = match.groups()
        start_sec = _parse_time(start_str)

        # 找到該時間點的說話者
        speaker = _find_speaker_at(start_sec, speakers)
        if speaker:
            result.append(f"[{start_str} - {end_str}] [{speaker}] {text}")
        else:
            result.append(line)

    return "\n".join(result)


def _find_speaker_at(time_sec: float, speakers: list[dict]) -> str | None:
    """找到指定時間點的說話者。

    Args:
        time_sec: 時間點（秒）。
        speakers: 說話者片段列表。

    Returns:
        說話者名稱，找不到則回傳 None。
    """
    for seg in speakers:
        if seg["start"] <= time_sec < seg["end"]:
            return seg["speaker"]
    return None


def _format_time(seconds: float) -> str:
    """將秒數格式化為 MM:SS。

    Args:
        seconds: 秒數。

    Returns:
        MM:SS 格式的時間字串。
    """
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def _parse_time(time_str: str) -> float:
    """將 MM:SS 格式解析為秒數。

    Args:
        time_str: MM:SS 格式的時間字串。

    Returns:
        秒數。
    """
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])
