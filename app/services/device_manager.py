"""GPU 裝置管理器。

集中管理 GPU 資源的偵測、分配與釋放。
支援 CUDA 自動偵測、OOM fallback、Ollama VRAM 釋放。
提供全域 GPU lock，確保 Whisper 和 Ollama 不同時佔用 GPU。
"""

import asyncio
import gc
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class DeviceManager:
    """GPU 裝置管理器（Singleton 模式）。

    職責：
    1. 偵測 CUDA 可用性，回傳適合的 device
    2. 釋放 GPU 記憶體（torch.cuda.empty_cache）
    3. OOM 後標記 CPU fallback（僅影響下次請求）
    4. Unload Ollama 模型以釋放 VRAM
    5. 追蹤目前使用的模型大小與降級原因
    6. 提供 VRAM 使用量查詢
    7. 建議模型降級順序
    """

    _force_cpu: bool = False
    _initialized: bool = False
    _current_model_size: str | None = None
    _last_fallback_reason: str | None = None
    _gpu_lock: asyncio.Lock | None = None

    @classmethod
    def get_gpu_lock(cls) -> asyncio.Lock:
        """取得全域 GPU lock，確保 Whisper 和 Ollama 不同時佔用 GPU。"""
        if cls._gpu_lock is None:
            cls._gpu_lock = asyncio.Lock()
        return cls._gpu_lock

    @classmethod
    def initialize(cls) -> None:
        """啟動時偵測 GPU 環境並 log 結果。僅執行一次。"""
        if cls._initialized:
            return
        cls._initialized = True

        valid_devices = {"auto", "cpu", "cuda"}
        if settings.DEVICE not in valid_devices:
            logger.warning(
                "DEVICE='%s' 不是有效值（%s），將使用 auto 模式",
                settings.DEVICE,
                "/".join(sorted(valid_devices)),
            )

        device = cls.get_device()

        if device == "cuda":
            try:
                import torch

                name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                vram_gb = props.total_mem / (1024**3)
                cuda_version = torch.version.cuda or "unknown"
                logger.info(
                    "GPU 偵測完成：Using device: cuda (%s, %.1f GB, CUDA %s)",
                    name,
                    vram_gb,
                    cuda_version,
                )
            except Exception:
                logger.info("Using device: cuda")
        else:
            # 檢查是否安裝了 CPU 版 PyTorch
            try:
                import torch  # noqa: F811

                if not torch.cuda.is_available():
                    logger.warning(
                        "PyTorch installed but CUDA not available. "
                        "To enable GPU: pip install torch --index-url "
                        "https://download.pytorch.org/whl/cu121"
                    )
            except ImportError:
                pass

            logger.info("Using device: cpu")

    @classmethod
    def get_device(cls) -> str:
        """根據設定與環境回傳適合的 device。

        Returns:
            "cuda" 或 "cpu"。

        Raises:
            RuntimeError: DEVICE=cuda 但 CUDA 不可用時。
        """
        if cls._force_cpu:
            return "cpu"

        if settings.DEVICE == "cpu":
            return "cpu"

        if settings.DEVICE == "cuda":
            try:
                import torch

                if not torch.cuda.is_available():
                    raise RuntimeError(
                        "DEVICE=cuda 但 CUDA 不可用，"
                        "請確認 NVIDIA 驅動與 PyTorch CUDA 版已安裝"
                    )
                return "cuda"
            except ImportError:
                raise RuntimeError(
                    "DEVICE=cuda 但 PyTorch 未安裝，請先安裝 PyTorch CUDA 版"
                )

        # auto 模式
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @classmethod
    def release_gpu_memory(cls) -> None:
        """釋放 PyTorch GPU cache 記憶體。"""
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
                logger.debug("GPU 記憶體已釋放")
        except ImportError:
            pass

    @classmethod
    def mark_cpu_fallback(cls) -> None:
        """OOM 後標記 CPU fallback（僅影響下次請求）。"""
        cls._force_cpu = True
        logger.warning(
            "GPU OOM detected — 已標記 CPU fallback，下次請求將使用 CPU。"
            "重啟 app 可重置此標記。"
        )

    @classmethod
    def reset_fallback(cls) -> None:
        """重置 CPU fallback 標記。"""
        cls._force_cpu = False

    @classmethod
    def set_current_model(cls, model_size: str | None) -> None:
        """記錄目前使用的 Whisper 模型大小。"""
        cls._current_model_size = model_size

    @classmethod
    def set_fallback_reason(cls, reason: str | None) -> None:
        """記錄最近一次降級原因。"""
        cls._last_fallback_reason = reason
        if reason:
            logger.warning("降級原因：%s", reason)

    @classmethod
    def get_status(cls) -> dict:
        """回傳目前裝置狀態資訊。"""
        device = cls.get_device()
        gpu_available = False
        gpu_name = None

        try:
            import torch

            gpu_available = torch.cuda.is_available()
            if gpu_available:
                gpu_name = torch.cuda.get_device_name(0)
        except ImportError:
            pass

        return {
            "device": device,
            "gpu_available": gpu_available,
            "gpu_name": gpu_name,
            "whisper_active_model": cls._current_model_size,
            "force_cpu_fallback": cls._force_cpu,
            "last_fallback_reason": cls._last_fallback_reason,
        }

    @classmethod
    def is_gpu_available(cls) -> bool:
        """檢查 GPU 是否可用且未被強制切換至 CPU。"""
        if cls._force_cpu:
            return False
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    @classmethod
    def get_vram_info(cls) -> dict:
        """回傳 GPU VRAM 使用量資訊。

        Returns:
            包含 total_gb 與 used_gb 的字典，無 GPU 時值為 None。
        """
        try:
            import torch

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                total_gb = round(props.total_mem / (1024**3), 2)
                used_bytes = torch.cuda.memory_allocated(0)
                used_gb = round(used_bytes / (1024**3), 2)
                return {"total_gb": total_gb, "used_gb": used_gb}
        except ImportError:
            pass
        return {"total_gb": None, "used_gb": None}

    @classmethod
    def suggest_model_fallback(
        cls, current_model: str, fallback_order: list[str]
    ) -> str | None:
        """回傳降級順序中的下一個可用模型。

        Args:
            current_model: 目前嘗試的模型大小。
            fallback_order: 降級順序列表。

        Returns:
            下一個較小的模型名稱，若已到最小則回傳 None。
        """
        try:
            idx = fallback_order.index(current_model)
            if idx + 1 < len(fallback_order):
                return fallback_order[idx + 1]
        except ValueError:
            pass
        return None

    @classmethod
    async def unload_ollama(cls) -> bool:
        """Unload Ollama 模型以釋放 VRAM。

        先透過 GET /api/ps 取得實際載入的模型，再逐一 unload。

        Returns:
            True 表示成功 unload 或無模型需要 unload。
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 取得目前載入的模型
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/ps")
                resp.raise_for_status()
                data = resp.json()

                models = data.get("models", [])
                if not models:
                    logger.debug("Ollama 無載入中的模型，跳過 unload")
                    return True

                # 逐一 unload
                for model_info in models:
                    model_name = model_info.get("name", "")
                    if not model_name:
                        continue

                    logger.info("Unloading Ollama 模型：%s", model_name)
                    unload_resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": model_name,
                            "keep_alive": 0,
                        },
                    )
                    unload_resp.raise_for_status()
                    logger.info("Ollama 模型 %s 已 unload", model_name)

                return True

        except Exception as e:
            logger.warning("Ollama unload 失敗：%s — 繼續處理（可能導致 VRAM 不足）", e)
            return False
