# Contract: Ollama Service API

**Date**: 2026-03-26 | **Branch**: 003-ollama-gpu-boost

## generate_summary(transcript: str) → dict | None

內部服務函式，透過 Ollama REST API 生成摘要。

### 行為變更

**變更前**:
- `OLLAMA_GPU=true` → 省略 `num_gpu`（Ollama 用 GPU）
- `OLLAMA_GPU=false` → `num_gpu: 0`（強制 CPU）

**變更後**:
- `OLLAMA_GPU=true` → 省略 `num_gpu`（強制 GPU）
- `OLLAMA_GPU=false` → `num_gpu: 0`（強制 CPU）
- `OLLAMA_GPU=auto` → 先嘗試省略 `num_gpu`，失敗時 fallback 到 `num_gpu: 0`

### 新增參數傳遞

```json
{
  "options": {
    "num_ctx": 16384,
    "num_gpu": 0,
    "num_thread": 16
  }
}
```

- `num_thread`: 當 `OLLAMA_NUM_THREAD > 0` 時傳遞

## POST /api/meetings/{id}/summarize

HTTP 端點，手動觸發重新生成摘要。

### 行為變更

**變更前**:
- 覆寫 summary，追加 action_items（不刪除舊的）

**變更後**:
- 先刪除舊 ActionItem 和 Topic
- 覆寫 summary 和 title
- 寫入新 action_items 和 semantic_analysis
- GPU auto 模式下自動選擇 GPU 或 CPU

### 回應格式（不變）

```json
{
  "detail": "摘要生成完成"
}
```

### 錯誤回應

| HTTP Status | 情境 |
|-------------|------|
| 503 | Ollama 服務不可用 |
| 404 | 會議紀錄不存在 |
| 400 | 會議沒有逐字稿 |
| 500 | Ollama 摘要生成失敗（含 GPU fallback 到 CPU 後仍失敗） |
