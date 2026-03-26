# Research: Ollama GPU 加速與模型升級

**Date**: 2026-03-26 | **Branch**: 003-ollama-gpu-boost

## R1: Ollama API GPU 控制機制

**Decision**: 透過 `num_gpu` 參數控制 Ollama 的 GPU/CPU 使用

**Rationale**:
- `num_gpu: 0` → 強制 CPU（目前 `OLLAMA_GPU=false` 的做法）
- 省略 `num_gpu` → Ollama 自動使用 GPU（預設行為）
- `num_gpu: -1` → 所有 GPU layers 都載入 GPU（可用於強制 GPU）
- 這是 per-request 設定，不需要 reload server

**Alternatives Considered**:
- 全域設定 Ollama 的 GPU → 不夠靈活，無法動態切換
- 用 `CUDA_VISIBLE_DEVICES` 環境變數 → 需要重啟 Ollama 服務，不適合動態場景

## R2: GPU 記憶體釋放流程

**Decision**: 沿用現有 `DeviceManager.release_gpu_memory()` 機制，Whisper 完成後自動釋放

**Rationale**:
- `local_whisper_provider.py:67-70` 的 `_release_model()` 已呼叫 `DeviceManager.release_gpu_memory()`
- `device_manager.py:124-134` 使用 `torch.cuda.empty_cache()` + `gc.collect()` 釋放 VRAM
- Whisper 模型設為 `None` 後 Python GC 會回收物件，`empty_cache()` 釋放 CUDA cache
- Ollama 也有 `unload_ollama()` 函式（`device_manager.py:229-270`），使用 `keep_alive: 0` 卸載模型

**Alternatives Considered**:
- 使用 `torch.cuda.mem_get_info()` 主動偵測可用 VRAM → 作為額外安全檢查保留，但不作為主要機制

## R3: GPU Lock 範圍需擴展

**Decision**: 將 Ollama GPU 摘要也納入 `_gpu_lock` 保護範圍

**Rationale**:
- 目前 `meeting_processor.py:99` 的 `_gpu_lock` 只保護 Whisper + Diarization
- Ollama 在 `auto` 模式使用 GPU 時，必須等 Whisper 釋放 VRAM 後才能開始
- 最簡單的做法：Ollama GPU 摘要也在 `_gpu_lock` 內執行，但放在 Whisper 之後（序列化）
- CPU 模式的 Ollama 不需要 lock

**Alternatives Considered**:
- 用獨立的 Ollama GPU lock → 增加複雜度，且 6GB VRAM 不允許同時跑兩個 GPU 任務
- 不加 lock，依靠 Ollama 自己的 OOM 處理 → 不可靠，可能導致 crash

## R4: 重新生成摘要的資料清理

**Decision**: 先刪除舊的 ActionItem、Topic、語意分析資料，再寫入新結果

**Rationale**:
- 目前 `meetings.py:284-293` 的 `/summarize` 端點只追加 ActionItem，不刪除舊的
- 資料庫關聯已設定 `cascade="all, delete-orphan"`，可安全刪除
- 需要清理的表：ActionItem、Topic（與 semantic_analysis 相關）
- Speaker 和 Utterance 來自 Diarization，不受摘要重新生成影響，應保留

**Alternatives Considered**:
- 版本化保留舊摘要 → 增加複雜度，使用者明確選擇「完全取代」

## R5: Config 三態設定實作

**Decision**: `OLLAMA_GPU` 從 `bool` 改為 `str`，支援 `auto`/`true`/`false`

**Rationale**:
- 目前 `config.py:52` 的 `OLLAMA_GPU: bool = False` 只支援二態
- Pydantic 的 `field_validator` 可驗證輸入值
- `auto` 為新預設值，讓系統自動判斷 GPU 可用性
- `ollama_service.py` 需要根據三態決定 `num_gpu` 參數

**Alternatives Considered**:
- 用 `Optional[bool]`（None = auto）→ `.env` 中不直覺
- 新增獨立的 `OLLAMA_GPU_AUTO` 布林值 → 多一個設定項，增加使用者困惑

## R6: VRAM 偵測用於 Fallback 決策

**Decision**: 在 `auto` 模式下嘗試 GPU，捕獲 Ollama 錯誤後退回 CPU

**Rationale**:
- `device_manager.py:188-205` 已有 `get_vram_info()` 但只回報 PyTorch 使用量
- Ollama 是獨立程序，其 VRAM 使用無法透過 PyTorch API 偵測
- 最可靠的方式：先嘗試 GPU（省略 `num_gpu`），如果 Ollama 回報錯誤則 fallback 到 CPU（`num_gpu: 0`）
- 可在嘗試前先用 `nvidia-smi` 或 `pynvml` 查詢，但增加依賴

**Alternatives Considered**:
- 安裝 `pynvml` 套件查詢真實 VRAM → 增加依賴，且 Ollama 的實際需求難以精確預估
- 固定 VRAM 閾值判斷 → 不同模型大小不同，維護困難
