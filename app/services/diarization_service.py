"""說話者辨識服務（Speaker Diarization）。

使用 pyannote.audio 進行本地端說話者辨識，支援 GPU 加速。
每次處理後釋放 Pipeline 與 GPU 記憶體，避免 VRAM 佔用。
自動偵測音檔中的說話者數量與發言時間段。
"""

import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.services.device_manager import DeviceManager

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """說話者片段。"""

    speaker: str
    start: float
    end: float


@dataclass
class UtteranceInfo:
    """結構化發言資訊（diarization + transcript 合併後）。"""

    speaker: str
    start_time: float
    end_time: float
    text: str
    order_index: int


# 預設調色盤（8 色循環）
SPEAKER_COLORS = [
    "#FF6B6B",  # 紅
    "#4ECDC4",  # 青
    "#45B7D1",  # 藍
    "#96CEB4",  # 綠
    "#FFEAA7",  # 黃
    "#DDA0DD",  # 紫
    "#F0B27A",  # 橙
    "#AED6F1",  # 淺藍
]


class DiarizationService:
    """說話者辨識服務。

    使用 pyannote.audio Pipeline 進行 speaker diarization。
    支援 GPU 加速，每次處理後釋放 Pipeline 與 GPU 記憶體。
    """

    def __init__(self) -> None:
        self._pipeline = None

    def is_available(self) -> bool:
        """檢查 diarization 服務是否可用。

        Returns:
            True 表示 pyannote 已安裝且 HF_TOKEN 已設定。
        """
        try:
            import pyannote.audio  # noqa: F401
        except ImportError:
            logger.warning("pyannote.audio 未安裝，說話者辨識不可用")
            return False

        if not settings.HF_TOKEN:
            logger.warning("HF_TOKEN 未設定，pyannote 模型授權不可用")
            return False

        return True

    def _load_pipeline(self):
        """載入 pyannote Pipeline 到適當的 device（每次處理重新載入）。"""
        from pyannote.audio import Pipeline

        device = DeviceManager.get_device()
        logger.info(
            "載入 pyannote speaker-diarization Pipeline (device=%s)...", device
        )
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.HF_TOKEN,
        )

        if device == "cuda":
            import torch

            pipeline.to(torch.device("cuda"))

        logger.info("pyannote Pipeline 載入完成")
        self._pipeline = pipeline
        return pipeline

    def _release_pipeline(self) -> None:
        """釋放 Pipeline 與 GPU 記憶體。"""
        self._pipeline = None
        DeviceManager.release_gpu_memory()

    async def diarize(
        self, file_path: str, num_speakers: int | None = None
    ) -> list[SpeakerSegment]:
        """執行說話者辨識。

        Args:
            file_path: 音檔路徑。
            num_speakers: 指定說話者人數，None 或 0 表示自動偵測。

        Returns:
            說話者片段列表，按時間排序。
            失敗時回傳空列表（graceful degradation）。
        """
        try:
            pipeline = self._load_pipeline()

            # 組裝 pipeline 參數
            params = {}
            if num_speakers and num_speakers > 0:
                params["num_speakers"] = num_speakers

            logger.info(
                "開始 diarization: %s (num_speakers=%s)",
                file_path,
                num_speakers or "auto",
            )

            # pyannote pipeline 是同步的，在 async context 中執行
            import asyncio

            loop = asyncio.get_event_loop()
            diarization = await loop.run_in_executor(
                None, lambda: pipeline(file_path, **params)
            )

            # 轉換為 SpeakerSegment 列表
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    SpeakerSegment(
                        speaker=speaker,
                        start=round(turn.start, 2),
                        end=round(turn.end, 2),
                    )
                )

            # 統一 speaker label 格式：SPEAKER_00 → Speaker_0
            unique_speakers = sorted(set(seg.speaker for seg in segments))
            label_map = {
                old: f"Speaker_{i}" for i, old in enumerate(unique_speakers)
            }
            for seg in segments:
                seg.speaker = label_map[seg.speaker]

            logger.info(
                "Diarization 完成：%d 個片段，%d 位說話者",
                len(segments),
                len(unique_speakers),
            )
            return segments

        except ImportError:
            logger.error("pyannote.audio 未安裝")
            return []
        except Exception as e:
            # OOM 時嘗試 CPU 重試
            params = {}
            if num_speakers and num_speakers > 0:
                params["num_speakers"] = num_speakers
            retry_result = self._handle_oom_and_retry(e, file_path, params)
            if retry_result is not None:
                return retry_result
            logger.exception("Diarization 執行失敗")
            return []
        finally:
            self._release_pipeline()

    def _handle_oom_and_retry(
        self, error: Exception, file_path: str, params: dict
    ) -> list[SpeakerSegment] | None:
        """檢查是否為 CUDA OOM，若是則退回 CPU 重試。

        Returns:
            CPU 重試成功時回傳 segments，否則回傳 None。
        """
        try:
            import torch

            if not isinstance(error, torch.cuda.OutOfMemoryError):
                return None
        except ImportError:
            return None

        logger.warning("pyannote CUDA OOM — 退回 CPU 模式重試 diarization")
        DeviceManager.set_fallback_reason("pyannote CUDA OOM, retrying on CPU")
        self._release_pipeline()

        try:
            from pyannote.audio import Pipeline

            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=settings.HF_TOKEN,
            )
            # 不呼叫 .to(cuda)，保持在 CPU
            self._pipeline = pipeline

            import asyncio

            loop = asyncio.get_event_loop()
            diarization = loop.run_in_executor(
                None, lambda: pipeline(file_path, **params)
            )
            # 注意：這裡在 sync context 中，無法 await
            # 改用同步方式
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(pipeline, file_path, **params)
                diarization_result = future.result()

            segments = []
            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                segments.append(
                    SpeakerSegment(
                        speaker=speaker,
                        start=round(turn.start, 2),
                        end=round(turn.end, 2),
                    )
                )

            # 統一 label
            unique_speakers = sorted(set(seg.speaker for seg in segments))
            label_map = {
                old: f"Speaker_{i}" for i, old in enumerate(unique_speakers)
            }
            for seg in segments:
                seg.speaker = label_map[seg.speaker]

            logger.info(
                "Diarization CPU 重試完成：%d 個片段，%d 位說話者",
                len(segments),
                len(unique_speakers),
            )
            return segments

        except Exception as cpu_err:
            logger.exception("Diarization CPU 重試也失敗：%s", cpu_err)
            return None
        finally:
            self._release_pipeline()

    def merge_with_transcript(
        self, segments: list[SpeakerSegment], transcript: str
    ) -> list[UtteranceInfo]:
        """將 diarization 結果與逐字稿按時間戳對齊。

        解析逐字稿中的時間戳格式 [MM:SS - MM:SS]，
        將每段文字配對到最接近的 speaker segment。

        Args:
            segments: diarization 產出的說話者片段。
            transcript: 帶時間戳的逐字稿文字。

        Returns:
            合併後的結構化發言列表。
        """
        if not segments or not transcript:
            return []

        # 解析逐字稿中的時間戳行
        # 格式：[MM:SS - MM:SS] 文字內容  或  [HH:MM:SS - HH:MM:SS] 文字內容
        time_pattern = re.compile(
            r"\[(\d{1,2}:?\d{2}:\d{2})\s*-\s*(\d{1,2}:?\d{2}:\d{2})\]\s*(.*)"
        )

        utterances = []
        for idx, line in enumerate(transcript.strip().split("\n")):
            line = line.strip()
            if not line:
                continue

            match = time_pattern.match(line)
            if not match:
                continue

            start_str, end_str, text = match.groups()
            start_sec = self._time_to_seconds(start_str)
            end_sec = self._time_to_seconds(end_str)

            # 找到與此時間段重疊最多的 speaker
            speaker = self._find_best_speaker(segments, start_sec, end_sec)

            utterances.append(
                UtteranceInfo(
                    speaker=speaker or "Unknown",
                    start_time=start_sec,
                    end_time=end_sec,
                    text=text.strip(),
                    order_index=idx,
                )
            )

        return utterances

    def _find_best_speaker(
        self, segments: list[SpeakerSegment], start: float, end: float
    ) -> str | None:
        """找到與指定時間段重疊最多的說話者。"""
        best_speaker = None
        best_overlap = 0.0

        for seg in segments:
            overlap_start = max(start, seg.start)
            overlap_end = min(end, seg.end)
            overlap = max(0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = seg.speaker

        return best_speaker

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """將時間字串轉換為秒數。

        支援 MM:SS 和 HH:MM:SS 格式。
        """
        parts = time_str.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0.0

    @staticmethod
    def get_speaker_color(index: int) -> str:
        """取得說話者的預設顏色。"""
        return SPEAKER_COLORS[index % len(SPEAKER_COLORS)]


# 模組級單例
diarization_service = DiarizationService()
