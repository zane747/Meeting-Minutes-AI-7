# Research: GPU 加速模型推論

**Feature**: 001-gpu-acceleration
**Date**: 2026-03-25

## R1: PyTorch CUDA 安裝方式

**Decision**: 透過 PyTorch 官方 CUDA wheel index URL 安裝 GPU 版 PyTorch，而非在 pyproject.toml 中直接指定 CUDA 版本。

**Rationale**:
- PyTorch CUDA 版本無法透過標準 pip/pyproject.toml 依賴指定（因為 wheel 托管在不同 index URL）
- 使用者需執行 `pip install torch --index-url https://download.pytorch.org/whl/cu121` 或 `cu124`
- 現有 `pyproject.toml` 的 `diarization` extra 已包含 `torch`（CPU 版），需在文件中明確指引 CUDA 版安裝步驟

**Alternatives considered**:
- 在 pyproject.toml 中使用 `--extra-index-url`：pip 不保證會從指定 index 下載，可能安裝 CPU 版
- 使用 conda 管理：增加額外工具鏈複雜度，不適合此專案

## R2: Whisper 模型大小與 VRAM 使用量

**Decision**: 建立模型降級順序 `large → medium → small → base → tiny`，OOM 時自動嘗試下一個較小的模型。

**Rationale**:
- Whisper 模型 VRAM 使用量（近似值）：
  - `large`: ~10GB（超出 6GB VRAM）
  - `medium`: ~5GB（適合 6GB VRAM，預設值）
  - `small`: ~2GB
  - `base`: ~1GB
  - `tiny`: ~0.5GB
- 使用者設定 `WHISPER_MODEL=medium` 為起始模型，OOM 時依序嘗試更小的模型
- 在 6GB VRAM 的 RTX 4050 上，`medium` 應可正常運行；若同時有其他程式佔用 VRAM，則可能需要降級

**Alternatives considered**:
- 固定使用 `small` 模型確保不會 OOM：犧牲品質
- 讓使用者手動選擇模型大小：違反「零設定體驗」的目標

## R3: 排隊機制實作方式

**Decision**: 使用 `asyncio.Lock` 實作簡單的互斥鎖，確保同一時間只有一個音檔在進行 GPU 推論。

**Rationale**:
- 專案為單機桌面應用，`asyncio.Lock` 即可滿足需求
- 現有 `process_meeting` 在 BackgroundTask 中執行，加鎖範圍為 GPU 推論部分（Whisper + Diarization）
- 不影響非 GPU 操作（如 Gemini 遠端模式、DB 操作）

**Alternatives considered**:
- 使用 Celery/Redis 任務佇列：過度工程化，單機不需要
- 使用 `threading.Lock`：FastAPI 基於 asyncio，應使用 async 原語

## R4: 系統狀態 API 設計

**Decision**: 新增 `GET /api/system/status` 端點，回傳 GPU 偵測結果、目前模式、VRAM 使用量等資訊。

**Rationale**:
- 符合 clarify 決議：提供 API 端點讓使用者主動查詢
- 沿用現有 `/api/` 前綴的路由命名慣例
- 回傳 JSON 格式，方便前端或使用者直接呼叫

**Alternatives considered**:
- 新增獨立的前端狀態頁面：增加前端開發工作，可後續擴充
- 整合至現有 `/api/meetings` 路由：職責不同，應分開

## R5: OOM 降級策略與 CPU Fallback

**Decision**: 兩階段降級策略 — (1) GPU 上嘗試更小模型 → (2) 所有模型都 OOM 才退回 CPU。

**Rationale**:
- 符合 clarify 決議：優先在 GPU 上使用較小模型
- GPU 上的 `small` 模型仍比 CPU 上的 `medium` 模型快數倍
- 降級紀錄寫入 log，並透過 API 可查詢目前模型狀態
- 降級僅影響當次請求，下次請求重新從使用者設定的模型大小開始

**Alternatives considered**:
- 降級後永久使用較小模型直到重啟：可能在暫時性 VRAM 佔用後永久降低品質
- 預先檢查 VRAM 可用量決定模型：不同模型的實際 VRAM 使用量因 batch 和音檔長度而異，預估不準確
