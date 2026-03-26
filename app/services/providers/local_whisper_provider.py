"""LocalWhisperProvider：透過本地端 Whisper 模型處理音檔。

使用 OpenAI Whisper 進行語音轉錄，支援 GPU 加速。
每次處理後釋放模型與 GPU 記憶體，避免 VRAM 佔用。
逐字稿保留原始語言，不強制轉為繁體中文。
若已配置 Ollama，可選配本地摘要功能。
"""

import asyncio
import logging
from functools import partial

import httpx

from app.config import settings
from app.core.exceptions import ProcessingError, ProviderUnavailableError
from app.services.device_manager import DeviceManager
from app.services.providers.base import (
    AudioProcessor,
    ProcessingContext,
    ProcessingResult,
)
from app.services.annotation_service import merge_transcript_with_speakers

logger = logging.getLogger(__name__)


class LocalWhisperProvider(AudioProcessor):
    """透過本地端 Whisper 模型處理音檔。

    Args:
        model_size: Whisper 模型大小（tiny/base/small/medium/large）。
    """

    def __init__(self, model_size: str = "base") -> None:
        """初始化 LocalWhisperProvider。

        Args:
            model_size: Whisper 模型大小。
        """
        self._model_size = model_size
        self._model = None

    def _load_model(self, model_size: str | None = None) -> None:
        """載入 Whisper 模型到適當的 device（每次處理重新載入）。

        Args:
            model_size: 指定載入的模型大小，None 則使用 self._model_size。

        Raises:
            ProviderUnavailableError: Whisper 套件未安裝。
        """
        size = model_size or self._model_size
        try:
            import whisper

            device = DeviceManager.get_device()
            logger.info("載入 Whisper 模型：%s (device=%s)", size, device)
            self._model = whisper.load_model(size, device=device)
            DeviceManager.set_current_model(size)
            logger.info("Whisper 模型載入完成")
        except ImportError:
            raise ProviderUnavailableError(
                "Whisper 未安裝，請執行 `pip install openai-whisper` 或切換遠端模式"
            )

    def _release_model(self) -> None:
        """釋放 Whisper 模型與 GPU 記憶體。"""
        self._model = None
        DeviceManager.release_gpu_memory()

    async def _transcribe_with_fallback(self, file_path: str) -> str:
        """執行 Whisper 轉錄，遇 OOM 自動降級至較小模型，最終退回 CPU。

        降級策略：
        1. 依 WHISPER_MODEL_FALLBACK_ORDER 嘗試更小的 GPU 模型
        2. 所有 GPU 模型均 OOM 時，退回 CPU 使用原始設定模型

        Args:
            file_path: 音檔路徑。

        Returns:
            格式化後的逐字稿。

        Raises:
            ProcessingError: 所有嘗試均失敗。
        """
        import torch

        fallback_order = settings.whisper_fallback_list
        # 從使用者設定的模型開始
        start_idx = 0
        try:
            start_idx = fallback_order.index(self._model_size)
        except ValueError:
            # 使用者設定的模型不在 fallback list 中，從頭開始
            pass

        models_to_try = fallback_order[start_idx:]

        # 階段一：在 GPU 上依序嘗試
        loop = asyncio.get_event_loop()
        use_fp16 = DeviceManager.get_device() == "cuda"

        for model_size in models_to_try:
            try:
                self._load_model(model_size)
                logger.info("開始轉錄音檔：%s (model=%s, fp16=%s)", file_path, model_size, use_fp16)
                result = await loop.run_in_executor(
                    None,
                    partial(self._model.transcribe, file_path, fp16=use_fp16),
                )
                transcript = self._format_transcript(result.get("segments", []))
                logger.info("Whisper 轉錄完成 (model=%s)", model_size)
                if model_size != self._model_size:
                    reason = f"CUDA OOM on {self._model_size}, downgraded to {model_size}"
                    DeviceManager.set_fallback_reason(reason)
                return transcript
            except torch.cuda.OutOfMemoryError:
                logger.warning(
                    "Whisper CUDA OOM (model=%s) — 嘗試更小模型", model_size
                )
                self._release_model()
                next_model = DeviceManager.suggest_model_fallback(
                    model_size, fallback_order
                )
                if next_model is None:
                    break  # 已到最小，進入 CPU fallback
                continue
            finally:
                self._release_model()

        # 階段二：CPU fallback — 使用原始設定模型
        logger.warning("所有 GPU 模型均 OOM，退回 CPU 模式 (model=%s)", self._model_size)
        DeviceManager.set_fallback_reason(
            f"All GPU models OOM, falling back to CPU with {self._model_size}"
        )
        try:
            import whisper

            device = "cpu"
            logger.info("載入 Whisper 模型：%s (device=%s)", self._model_size, device)
            self._model = whisper.load_model(self._model_size, device=device)
            DeviceManager.set_current_model(self._model_size)
            result = await loop.run_in_executor(
                None,
                partial(self._model.transcribe, file_path, fp16=False),
            )
            transcript = self._format_transcript(result.get("segments", []))
            logger.info("Whisper CPU 轉錄完成 (model=%s)", self._model_size)
            return transcript
        except Exception as e:
            raise ProcessingError(f"Whisper CPU fallback 也失敗：{e}") from e
        finally:
            self._release_model()

    def _format_transcript(self, segments: list[dict]) -> str:
        """將 Whisper segments 格式化為段落式時間戳記逐字稿。

        Args:
            segments: Whisper 輸出的 segments 列表。

        Returns:
            格式化後的逐字稿文字。
        """
        lines = []
        for seg in segments:
            start = self._format_time(seg["start"])
            end = self._format_time(seg["end"])
            text = seg["text"].strip()
            if text:
                lines.append(f"[{start} - {end}] {text}")
        return "\n".join(lines)

    @staticmethod
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

    async def process(
        self, file_path: str, context: ProcessingContext | None = None
    ) -> ProcessingResult:
        """處理音檔，回傳統一格式的結果。

        支援 ProcessingContext：
        - 有 TextGrid 逐字稿 + skip_transcription → 跳過 Whisper
        - 有 RTTM speakers → 後處理合併角色標籤
        - 無 context → 照常 Whisper 轉錄

        Args:
            file_path: 音訊檔案的路徑。
            context: 標註檔上下文，可選。

        Returns:
            包含逐字稿（及可選的摘要與 Action Items）的 ProcessingResult。

        Raises:
            ProviderUnavailableError: Whisper 未安裝。
            ProcessingError: 轉錄失敗。
        """
        try:
            # A) 有 TextGrid 逐字稿 + 跳過轉錄
            if context and context.skip_transcription and context.transcript:
                logger.info("使用 TextGrid 逐字稿，跳過 Whisper 轉錄")
                transcript = context.transcript
            else:
                # B) Whisper 轉錄（GPU 加速 + OOM 自動降級）
                # Ollama 可能佔用 GPU，Whisper 前先卸載（auto/true 模式）
                ollama_gpu_mode = settings.OLLAMA_GPU.lower()
                if (
                    DeviceManager.get_device() == "cuda"
                    and settings.OLLAMA_ENABLED
                    and ollama_gpu_mode in ("true", "auto")
                ):
                    await DeviceManager.unload_ollama()

                transcript = await self._transcribe_with_fallback(file_path)

            # C) 有 RTTM speakers → 後處理合併角色標籤
            if context and context.speakers:
                transcript = merge_transcript_with_speakers(
                    transcript, context.speakers
                )
                logger.info("RTTM 角色標籤已合併至逐字稿")

            # D) 回傳逐字稿（Ollama 摘要由 meeting_processor 在 GPU lock 外呼叫）
            return ProcessingResult(transcript=transcript)

        except ProviderUnavailableError:
            raise
        except Exception as e:
            raise ProcessingError(f"Whisper 處理失敗：{e}") from e

    @staticmethod
    def _handle_oom(error: Exception) -> None:
        """檢查是否為 CUDA OOM，若是則標記 CPU fallback。"""
        try:
            import torch

            if isinstance(error, torch.cuda.OutOfMemoryError):
                DeviceManager.mark_cpu_fallback()
                logger.error(
                    "Whisper CUDA OOM — VRAM 不足，已切換為 CPU 模式，請重新提交"
                )
        except ImportError:
            pass

    def get_provider_name(self) -> str:
        """回傳 Provider 名稱。"""
        if settings.OLLAMA_ENABLED:
            return "Whisper + Ollama (Local)"
        return "Whisper (Local)"

    async def health_check(self) -> bool:
        """檢查 Whisper 套件與 Ollama 可用性。

        Returns:
            True 表示 Whisper 可用。
        """
        # 檢查 whisper 套件
        try:
            import whisper  # noqa: F401
        except ImportError:
            logger.warning("Whisper 套件未安裝")
            return False

        # 檢查 Ollama（若啟用）
        if settings.OLLAMA_ENABLED:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"{settings.OLLAMA_BASE_URL}/api/tags"
                    )
                    resp.raise_for_status()
                    logger.info("Ollama 服務可用")
            except Exception as e:
                logger.warning(f"Ollama 服務不可用：{e}")

        return True
