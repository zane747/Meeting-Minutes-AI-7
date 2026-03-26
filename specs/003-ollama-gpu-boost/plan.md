# Implementation Plan: Ollama GPU 加速與模型升級

**Branch**: `003-ollama-gpu-boost` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-ollama-gpu-boost/spec.md`

## Summary

將 Ollama 摘要服務從純 CPU 執行改為支援 GPU 加速，並新增三態 GPU 設定（auto/true/false）。`auto` 模式下，系統在 Whisper 轉錄完成並釋放 VRAM 後，自動將 Ollama 切換至 GPU 執行摘要。同時支援設定 CPU 執行緒數和更大的 context window，以支援更強的模型（gemma2 9B）和更長的逐字稿。重新生成摘要時完全取代舊資料。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, httpx, SQLAlchemy (aiosqlite), pydantic-settings, PyTorch (CUDA)
**Storage**: SQLite (aiosqlite)
**Testing**: pytest
**Target Platform**: Windows 11 (NVIDIA RTX 4050 Laptop, 6GB VRAM)
**Project Type**: Web service (FastAPI)
**Performance Goals**: GPU 模式下摘要生成 < 1 分鐘（40 分鐘音檔）
**Constraints**: 6GB VRAM 限制，Whisper 和 Ollama 必須序列使用 GPU
**Scale/Scope**: 單用戶本地部署

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution 為空模板，無具體 gate 需檢查。以 spec 中的需求為準。

## Project Structure

### Documentation (this feature)

```text
specs/003-ollama-gpu-boost/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: Research findings
├── data-model.md        # Phase 1: Data model changes
├── quickstart.md        # Phase 1: Quick start guide
├── contracts/
│   └── ollama-api.md    # Phase 1: API contract changes
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
app/
├── config.py                          # 修改：OLLAMA_GPU 三態、OLLAMA_NUM_THREAD
├── services/
│   ├── ollama_service.py              # 修改：GPU auto fallback、num_thread、截斷、timeout
│   ├── device_manager.py              # 修改：新增 GPU 可用性檢查輔助方法
│   └── meeting_processor.py           # 修改：Ollama GPU 摘要納入 _gpu_lock
├── api/routes/
│   └── meetings.py                    # 修改：/summarize 端點刪除舊資料後寫入新結果
└── services/providers/
    └── local_whisper_provider.py      # 修改：Ollama GPU auto 模式整合
```

**Structure Decision**: 無需新增檔案或目錄，所有變更在既有程式碼上進行。

## Complexity Tracking

無 Constitution 違規需要記錄。

## Implementation Phases

### Phase A: Config 三態設定（FR-001, FR-002, FR-003）

1. `app/config.py`:
   - `OLLAMA_GPU: bool` → `OLLAMA_GPU: str = "auto"`
   - 新增 `field_validator` 驗證 `auto`/`true`/`false`
   - `OLLAMA_NUM_THREAD: int = 0` 已加入
   - `OLLAMA_NUM_CTX: int = 16384` 已更新

2. `.env` 和 `.env.example`:
   - `OLLAMA_GPU=auto`
   - `OLLAMA_NUM_THREAD=16`
   - `OLLAMA_MODEL=gemma2:latest`

### Phase B: Ollama Service GPU Auto Fallback（FR-001, FR-004, FR-006, FR-007）

1. `app/services/ollama_service.py`:
   - 根據 `OLLAMA_GPU` 三態決定 `num_gpu` 參數：
     - `"false"` → `num_gpu: 0`
     - `"true"` → 省略 `num_gpu`
     - `"auto"` → 先嘗試省略 `num_gpu`，HTTP 錯誤或 Ollama 錯誤時 retry with `num_gpu: 0`
   - 逐字稿截斷保護（已實作）
   - timeout 600s（已實作）
   - `num_thread` 傳遞（已實作）

### Phase C: GPU Lock 擴展（FR-005, FR-008）

1. `app/services/meeting_processor.py`:
   - Ollama GPU 摘要（`auto` 或 `true` 模式）納入 `_gpu_lock`
   - CPU 模式的 Ollama 不需要 lock（可在 lock 外執行）

2. `app/services/providers/local_whisper_provider.py`:
   - 在 Whisper 處理完且 VRAM 釋放後，Ollama 摘要根據 GPU 模式決定是否取得 lock

### Phase D: 重新生成摘要資料清理（FR-009）

1. `app/api/routes/meetings.py`:
   - `/summarize` 端點在寫入新結果前，先刪除舊 ActionItem 和 Topic
   - 使用 SQLAlchemy 批次刪除
   - 覆寫 summary 和 title

### Phase E: 驗證與測試

1. 手動測試：上傳音檔，觀察 GPU → CPU 自動切換
2. 驗證 `nvidia-smi` VRAM 變化符合預期
3. 測試三態設定各模式的行為
4. 測試重新生成摘要的資料清理
