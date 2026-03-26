# Quickstart: GPU 加速模型推論

**Feature**: 001-gpu-acceleration
**Date**: 2026-03-25

## 前置條件

1. NVIDIA GPU（支援 CUDA）
2. NVIDIA 驅動程式已安裝
3. Python 3.11+
4. 專案已 clone 並建立虛擬環境

## 安裝步驟

### 1. 安裝 PyTorch CUDA 版

```bash
# CUDA 12.1（推薦）
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 或 CUDA 12.4
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

### 2. 安裝本地模式依賴

```bash
pip install openai-whisper
```

### 3. （可選）安裝說話者辨識

```bash
pip install pyannote.audio
```

### 4. 設定環境變數

```env
MODEL_MODE=local
DEVICE=auto
WHISPER_MODEL=medium
```

## 驗證 GPU 是否正常運作

### 方式一：啟動應用程式

```bash
uvicorn app.main:app --reload
```

觀察 log 輸出應包含：
```
GPU 偵測完成：Using device: cuda (NVIDIA GeForce RTX 4050 Laptop GPU, 6.0 GB)
```

### 方式二：查詢系統狀態 API

```bash
curl http://localhost:8000/api/system/status
```

回傳 JSON 中 `device` 應為 `"cuda"`，`gpu_available` 應為 `true`。

### 方式三：Python 快速檢查

```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Device: {torch.cuda.get_device_name(0)}")
```

## 常見問題

### GPU 偵測失敗（顯示 cpu）

1. 確認 NVIDIA 驅動已安裝：`nvidia-smi`
2. 確認 PyTorch 為 CUDA 版：`python -c "import torch; print(torch.version.cuda)"`
3. 若顯示 `None`，重新安裝 CUDA 版 PyTorch（見步驟 1）

### VRAM 不足（OOM）

- 系統會自動嘗試較小的 Whisper 模型
- 可手動在 `.env` 中設定 `WHISPER_MODEL=small` 使用更小模型
- 確認其他程式（如遊戲、其他 AI 模型）未佔用 GPU 記憶體

### 強制使用 CPU

```env
DEVICE=cpu
```
