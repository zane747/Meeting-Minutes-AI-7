# Research: GPU/CPU 工作負載分工最佳化

**Date**: 2026-03-26
**Branch**: `002-gpu-cpu-workload-split`

## R-001: Ollama num_gpu 參數控制 GPU/CPU 分配

**Decision**: 使用 Ollama REST API 的 `num_gpu` 選項控制 GPU 層數分配

**Rationale**:
- Ollama `/api/chat` endpoint 的 `options` 物件支援 `num_gpu` 參數
- `num_gpu: 0` = 所有層在 CPU 上推論（完全不使用 GPU）
- `num_gpu` 省略或設為正整數 = 自動或指定 GPU 層數
- 此參數輕量、不影響模型行為，只改變硬體分配
- 現有程式碼 (`ollama_service.py:82-84`) 已有 `options` 物件，只需新增一行

**Alternatives considered**:
- 環境變數 `CUDA_VISIBLE_DEVICES=""` — 影響整個程序，會連 Whisper 也無法用 GPU，不可行
- Ollama 啟動參數 `--num-gpu 0` — 需要重啟 Ollama 服務，不夠靈活
- 不同 Ollama instance 分別跑 GPU/CPU — 過於複雜

**Implementation detail**:
```json
{
  "options": {
    "num_ctx": 8192,
    "num_gpu": 0
  }
}
```

## R-002: Whisper 轉錄前是否需要 unload Ollama

**Decision**: 當 `OLLAMA_GPU=false` 時，不需要 unload Ollama（因為 Ollama 不佔 GPU）；當 `OLLAMA_GPU=true` 時，保留 unload 行為

**Rationale**:
- `num_gpu: 0` 時 Ollama 完全不佔用 VRAM，Whisper 可獨佔 GPU
- 省去 unload → Whisper → reload 的開銷
- `OLLAMA_GPU=true` 時 Ollama 佔 VRAM，需要在 Whisper 前 unload

**Alternatives considered**:
- 永遠 unload — 不必要的開銷（OLLAMA_GPU=false 時）
- 永遠不 unload — OLLAMA_GPU=true 時會 VRAM 不足

## R-003: OLLAMA_GPU 設定參數設計

**Decision**: 新增 `OLLAMA_GPU` boolean 設定（預設 `false`），控制 Ollama 是否使用 GPU

**Rationale**:
- 簡單的 boolean 開關，對使用者友善
- 預設 `false` 適合大多數消費級 GPU（6-8GB VRAM）
- 大 VRAM 使用者可設為 `true` 取得更快摘要速度
- 與現有 `DEVICE` 設定不衝突（`DEVICE` 控制 Whisper/Diarization，`OLLAMA_GPU` 只控制 Ollama）

**Alternatives considered**:
- Auto mode（根據 VRAM 餘量判斷）— 判斷邏輯複雜，不同模型 VRAM 需求不同，難以準確預估
- 使用既有 `DEVICE` 參數 — 語意不同，DEVICE 影響全域，但需求是 Ollama 獨立控制

## R-004: Diarization 裝置分配（已確認）

**Decision**: Diarization (pyannote) 維持 GPU 執行，與 Whisper 共用 GPU lock

**Rationale**:
- pyannote 從 GPU 加速獲益顯著
- 已有 GPU lock 確保 Whisper 與 Diarization 不同時佔用 GPU
- Diarization 在 Whisper 之前執行，不會互相搶佔
- 現有 OOM fallback 機制已處理 VRAM 不足情況
