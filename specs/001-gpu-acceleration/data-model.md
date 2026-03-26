# Data Model: GPU 加速模型推論

**Feature**: 001-gpu-acceleration
**Date**: 2026-03-25

## 概述

本功能不新增資料庫表或持久化實體。所有新增狀態皆為運行時記憶體狀態（in-memory），隨應用程式重啟而重置。

## 運行時狀態實體

### DeviceManager（擴充現有 Singleton）

| 屬性 | 型別 | 說明 |
|------|------|------|
| `_force_cpu` | `bool` | OOM 後強制 CPU 模式（現有） |
| `_initialized` | `bool` | 是否已初始化（現有） |
| `_current_model_size` | `str \| None` | 目前 Whisper 使用的模型大小（新增） |
| `_last_fallback_reason` | `str \| None` | 最近一次降級原因（新增） |

### SystemStatus（新增 Response Schema）

| 欄位 | 型別 | 說明 |
|------|------|------|
| `device` | `str` | 目前使用的裝置（"cuda" / "cpu"） |
| `gpu_available` | `bool` | GPU 是否可用 |
| `gpu_name` | `str \| None` | GPU 型號名稱 |
| `gpu_vram_total_gb` | `float \| None` | GPU 總 VRAM (GB) |
| `gpu_vram_used_gb` | `float \| None` | GPU 已使用 VRAM (GB) |
| `whisper_model` | `str` | 設定的 Whisper 模型大小 |
| `whisper_active_model` | `str \| None` | 實際使用的模型大小（降級後可能不同） |
| `force_cpu_fallback` | `bool` | 是否因 OOM 強制使用 CPU |
| `last_fallback_reason` | `str \| None` | 最近降級原因 |
| `ollama_enabled` | `bool` | Ollama 是否啟用 |
| `diarization_enabled` | `bool` | Diarization 是否啟用 |

### Whisper 模型降級順序

```text
large → medium → small → base → tiny → CPU fallback
```

降級觸發條件：`torch.cuda.OutOfMemoryError`
降級範圍：僅影響當次請求，下次請求從使用者設定的模型大小重新開始。

## 狀態轉換

```text
啟動
  ↓
[DeviceManager.initialize()]
  ↓
偵測 CUDA → 設定 device = "cuda" 或 "cpu"
  ↓
收到處理請求
  ↓
取得 asyncio.Lock（排隊等待）
  ↓
Unload Ollama（若 CUDA + Ollama 啟用）
  ↓
載入模型（使用者設定大小）
  ↓
[OOM?] → 嘗試較小模型 → [仍 OOM?] → CPU fallback
  ↓
處理完成 → 釋放模型 + GPU 記憶體 → 釋放 Lock
```
