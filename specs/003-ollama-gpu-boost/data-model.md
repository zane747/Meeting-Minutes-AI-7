# Data Model: Ollama GPU 加速與模型升級

**Date**: 2026-03-26 | **Branch**: 003-ollama-gpu-boost

## 變更的實體

### Settings（app/config.py）

| 欄位 | 變更前 | 變更後 | 說明 |
|------|--------|--------|------|
| `OLLAMA_GPU` | `bool = False` | `str = "auto"` | 三態：auto/true/false |
| `OLLAMA_NUM_THREAD` | （新增） | `int = 0` | CPU 執行緒數，0 = 自動 |
| `OLLAMA_NUM_CTX` | `int = 8192` | `int = 16384` | 加大 context window |

**驗證規則**:
- `OLLAMA_GPU` 必須為 `"auto"`、`"true"` 或 `"false"`（不區分大小寫）
- `OLLAMA_NUM_THREAD` 必須 ≥ 0

### Meeting（既有，無結構變更）

重新生成摘要時的資料清理流程：
1. 刪除該會議所有 ActionItem
2. 刪除該會議所有 Topic
3. 覆寫 `meeting.summary`
4. 覆寫 `meeting.title`（若 AI 建議新標題）
5. 保留 Speaker、Utterance（來自 Diarization，不受影響）

### Ollama API 請求 Options

| 參數 | `OLLAMA_GPU=false` | `OLLAMA_GPU=true` | `OLLAMA_GPU=auto` |
|------|-------------------|-------------------|-------------------|
| `num_gpu` | `0`（強制 CPU） | 省略（Ollama 預設用 GPU） | 動態決定：GPU 可用時省略，失敗時 fallback `0` |
| `num_thread` | 依設定值 | 依設定值 | 依設定值 |
| `num_ctx` | 依設定值 | 依設定值 | 依設定值 |

## 狀態轉換

### Ollama GPU Auto 模式決策流程

```
OLLAMA_GPU=auto
    │
    ├─ GPU 閒置（Whisper 未在跑）
    │   └─ 嘗試 GPU 模式（省略 num_gpu）
    │       ├─ 成功 → 完成
    │       └─ 失敗 → Fallback CPU（num_gpu: 0）→ 完成
    │
    └─ GPU 忙碌（Whisper 正在跑）
        └─ 等待 _gpu_lock 釋放
            └─ GPU 釋放後 → 嘗試 GPU 模式 → 同上
```

## 不受影響的實體

- **Speaker**: Diarization 產出，摘要重新生成不影響
- **Utterance**: Diarization 產出，摘要重新生成不影響
- **Meeting 核心欄位**: id, file_path, status, transcript 等不受影響
