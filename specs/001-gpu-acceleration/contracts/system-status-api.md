# Contract: System Status API

**Feature**: 001-gpu-acceleration
**Date**: 2026-03-25

## GET /api/system/status

查詢系統運算資源狀態。

### Response 200

```json
{
  "device": "cuda",
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4050 Laptop GPU",
  "gpu_vram_total_gb": 6.0,
  "gpu_vram_used_gb": 1.2,
  "whisper_model": "medium",
  "whisper_active_model": "medium",
  "force_cpu_fallback": false,
  "last_fallback_reason": null,
  "ollama_enabled": true,
  "diarization_enabled": false
}
```

### Response 200（無 GPU）

```json
{
  "device": "cpu",
  "gpu_available": false,
  "gpu_name": null,
  "gpu_vram_total_gb": null,
  "gpu_vram_used_gb": null,
  "whisper_model": "medium",
  "whisper_active_model": null,
  "force_cpu_fallback": false,
  "last_fallback_reason": null,
  "ollama_enabled": true,
  "diarization_enabled": false
}
```

### Response 200（OOM 降級後）

```json
{
  "device": "cuda",
  "gpu_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4050 Laptop GPU",
  "gpu_vram_total_gb": 6.0,
  "gpu_vram_used_gb": 5.8,
  "whisper_model": "medium",
  "whisper_active_model": "small",
  "force_cpu_fallback": false,
  "last_fallback_reason": "CUDA OOM on medium model, downgraded to small",
  "ollama_enabled": true,
  "diarization_enabled": false
}
```

## 欄位說明

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `device` | string | Y | 目前使用裝置："cuda" 或 "cpu" |
| `gpu_available` | boolean | Y | CUDA 是否可用 |
| `gpu_name` | string\|null | Y | GPU 名稱，無 GPU 時為 null |
| `gpu_vram_total_gb` | number\|null | Y | GPU 總 VRAM (GB) |
| `gpu_vram_used_gb` | number\|null | Y | GPU 已使用 VRAM (GB) |
| `whisper_model` | string | Y | 使用者設定的 Whisper 模型大小 |
| `whisper_active_model` | string\|null | Y | 最近一次實際使用的模型大小 |
| `force_cpu_fallback` | boolean | Y | 是否已觸發 CPU fallback |
| `last_fallback_reason` | string\|null | Y | 最近一次降級原因 |
| `ollama_enabled` | boolean | Y | Ollama 服務是否啟用 |
| `diarization_enabled` | boolean | Y | 說話者辨識是否啟用 |
