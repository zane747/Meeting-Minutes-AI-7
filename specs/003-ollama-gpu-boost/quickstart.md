# Quickstart: Ollama GPU 加速與模型升級

**Branch**: 003-ollama-gpu-boost

## 前置需求

- Ollama 已安裝且服務運行中
- `gemma2:latest` 模型已下載：`ollama pull gemma2:latest`
- NVIDIA GPU 驅動已安裝（CUDA 支援）

## 設定

在 `.env` 中設定：

```env
OLLAMA_ENABLED=true
OLLAMA_MODEL=gemma2:latest
OLLAMA_GPU=auto           # auto = 自動偵測 GPU | true = 強制 GPU | false = 強制 CPU
OLLAMA_NUM_CTX=16384
OLLAMA_NUM_THREAD=16      # CPU 核心數，0 = 自動
```

## 驗證步驟

1. 啟動服務：`python -m uvicorn app.main:app --reload`
2. 上傳一段音檔（本地模式）
3. 觀察終端日誌：
   - Whisper 轉錄完成 → GPU 記憶體釋放
   - Ollama 摘要開始 → 應看到 GPU 模式（auto 下）
4. 用 `nvidia-smi` 確認 VRAM 使用量變化

## 預期行為

| 階段 | GPU 使用 | VRAM 佔用 |
|------|----------|-----------|
| Whisper 轉錄 | ~25-38% | ~4.5 GB |
| Whisper 完成 | 0% | ~0 MB（釋放後） |
| Ollama 摘要 (GPU) | 高 | ~5 GB |
| Ollama 摘要 (CPU fallback) | 0% | 0 MB |
