# Implementation Plan: GPU/CPU 工作負載分工最佳化

**Branch**: `002-gpu-cpu-workload-split` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-gpu-cpu-workload-split/spec.md`

## Summary

消除 Whisper 與 Ollama 搶佔同一 GPU 導致的模型反覆載入/卸載開銷。將 Whisper/Diarization 綁定 GPU（效能提升顯著），Ollama 預設 CPU（模型小，CPU 可接受），並提供 `OLLAMA_GPU` 設定讓大 VRAM 使用者切換。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, OpenAI Whisper, pyannote.audio, PyTorch (CUDA), Ollama (REST API), httpx
**Storage**: SQLite (aiosqlite) — 無 schema 變更
**Testing**: 手動驗證（nvidia-smi + 功能測試）
**Target Platform**: Windows 11（本地桌面應用）
**Project Type**: Web service（本地 FastAPI 伺服器）
**Performance Goals**: 消除每次處理的模型 swap 開銷（約 10-30 秒）
**Constraints**: RTX 4050 6GB VRAM，Whisper medium + gemma2:2b 需共存
**Scale/Scope**: 單使用者本地應用

## Constitution Check

*Constitution 為預設模板（未自訂），無特定 gate 需要檢查。*

**Status**: PASS — 無違規項目

## Project Structure

### Documentation (this feature)

```text
specs/002-gpu-cpu-workload-split/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
app/
├── config.py                              # 新增 OLLAMA_GPU 設定
├── services/
│   ├── ollama_service.py                  # 加入 num_gpu 條件邏輯
│   └── providers/
│       └── local_whisper_provider.py      # 條件化 unload_ollama()
.env.example                               # 新增 OLLAMA_GPU 文件
```

**Structure Decision**: 現有結構不變，僅修改 3 個原始碼檔案 + 1 個設定範例檔。

## Complexity Tracking

無違規，不需要追蹤。
