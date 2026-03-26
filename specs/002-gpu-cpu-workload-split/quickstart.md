# Quickstart: GPU/CPU 工作負載分工最佳化

**Branch**: `002-gpu-cpu-workload-split`

## 目標

將 Whisper/Diarization 綁定 GPU、Ollama 預設 CPU，消除 VRAM 搶佔。

## 變更範圍（3 個檔案）

1. **`app/config.py`** — 新增 `OLLAMA_GPU: bool = False`
2. **`app/services/ollama_service.py`** — API options 加入 `num_gpu` 條件邏輯
3. **`app/services/providers/local_whisper_provider.py`** — 條件化 `unload_ollama()` 呼叫

## 附帶更新

4. **`.env.example`** — 新增 `OLLAMA_GPU=false` 文件
5. **`.env`** — 新增 `OLLAMA_GPU=false`

## 驗證方式

1. 啟動伺服器，上傳音檔使用本地模式
2. 確認 `nvidia-smi` 中 Ollama 不佔 GPU（OLLAMA_GPU=false 時）
3. 確認處理正常完成，逐字稿與摘要均產出
4. 設定 `DEVICE=cpu` 測試純 CPU 模式

## 不變的部分

- Diarization 裝置分配邏輯（維持使用 DeviceManager.get_device()）
- GPU lock 機制
- OOM fallback 機制
- 遠端模式（Gemini Provider）
