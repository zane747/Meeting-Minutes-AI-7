# Data Model: GPU/CPU 工作負載分工最佳化

**Date**: 2026-03-26
**Branch**: `002-gpu-cpu-workload-split`

## 變更摘要

此功能不新增資料庫實體，僅涉及設定層與服務層的變更。

## 設定實體

### Settings（app/config.py）

| 欄位 | 類型 | 預設值 | 說明 |
| ---- | ---- | ------ | ---- |
| `OLLAMA_GPU` | `bool` | `false` | 控制 Ollama 是否使用 GPU 推論 |

**狀態轉換**: 無（靜態設定，啟動時讀取）

**驗證規則**: 標準 boolean 值（true/false）

**與既有設定的關係**:
- `DEVICE` — 控制 Whisper 與 Diarization 的裝置（auto/cpu/cuda），不受 OLLAMA_GPU 影響
- `OLLAMA_ENABLED` — 控制 Ollama 功能開關，OLLAMA_GPU 僅在 OLLAMA_ENABLED=true 時有意義
- `OLLAMA_GPU` — 獨立控制 Ollama 的 GPU/CPU 選擇

### 裝置分配矩陣

| 元件 | DEVICE=auto (有 GPU) | DEVICE=cpu | OLLAMA_GPU=false | OLLAMA_GPU=true |
| ---- | -------------------- | ---------- | ---------------- | --------------- |
| Whisper | GPU | CPU | 不影響 | 不影響 |
| Diarization | GPU | CPU | 不影響 | 不影響 |
| Ollama | 依 OLLAMA_GPU | CPU | CPU (num_gpu=0) | GPU (預設行為) |

## 服務層變更

### OllamaService（app/services/ollama_service.py）

**變更**: API 呼叫的 `options` 物件根據 `OLLAMA_GPU` 設定動態加入 `num_gpu` 參數

- `OLLAMA_GPU=false` → `options.num_gpu = 0`（強制 CPU）
- `OLLAMA_GPU=true` → 不傳 `num_gpu`（Ollama 自動分配）

### LocalWhisperProvider（app/services/providers/local_whisper_provider.py）

**變更**: 條件化 `unload_ollama()` 呼叫

- `OLLAMA_GPU=false` → 跳過 `unload_ollama()`（Ollama 不佔 GPU）
- `OLLAMA_GPU=true` → 保留 `unload_ollama()`（需釋放 VRAM 給 Whisper）
