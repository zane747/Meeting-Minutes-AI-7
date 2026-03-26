# Implementation Plan: GPU 加速模型推論

**Branch**: `001-gpu-acceleration` | **Date**: 2026-03-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-gpu-acceleration/spec.md`

## Summary

讓本地端 Whisper 語音轉文字與 pyannote 說話者辨識模型充分利用 NVIDIA GPU（CUDA）加速，大幅提升處理效率。專案已有 DeviceManager 架構與 CUDA 偵測機制，但目前 PyTorch 安裝為 CPU 版本，且缺少 VRAM 不足時的模型自動降級策略與系統狀態查詢端點。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, OpenAI Whisper, pyannote.audio, PyTorch (CUDA), Ollama (REST API), SQLAlchemy
**Storage**: SQLite (aiosqlite)
**Testing**: pytest, pytest-asyncio
**Target Platform**: Windows 桌面環境 (NVIDIA RTX 4050, 6GB VRAM)
**Project Type**: Web Service (FastAPI + Jinja2 templates)
**Performance Goals**: 10 分鐘音檔轉文字 < 3 分鐘（GPU 模式），比 CPU 快 50%+
**Constraints**: 6GB VRAM 限制，需與 Ollama 協調 VRAM 使用
**Scale/Scope**: 單機桌面使用，嚴格排隊一次處理一個音檔

## Constitution Check

*GATE: Constitution 為空白模板（未填寫），無約束需檢查。直接通過。*

## Project Structure

### Documentation (this feature)

```text
specs/001-gpu-acceleration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
app/
├── api/
│   └── routes/
│       ├── meetings.py         # 現有 - 會議 API
│       ├── pages.py            # 現有 - 頁面路由
│       └── system.py           # 新增 - 系統狀態 API 端點
├── config.py                   # 修改 - 新增 WHISPER_MODEL_FALLBACK_ORDER 設定
├── main.py                     # 修改 - 註冊 system router
├── services/
│   ├── device_manager.py       # 修改 - 新增 VRAM 查詢、模型降級建議
│   ├── meeting_processor.py    # 修改 - 整合排隊機制與降級邏輯
│   ├── providers/
│   │   └── local_whisper_provider.py  # 修改 - OOM 時自動降級模型大小
│   ├── diarization_service.py  # 修改 - OOM 時降級處理
│   └── ollama_service.py       # 現有 - 不修改
├── models/
│   └── schemas.py              # 修改 - 新增 SystemStatusResponse
└── templates/
    └── (不修改)

pyproject.toml                  # 修改 - torch CUDA 安裝指引
.env.example                    # 修改 - 文件補充
```

**Structure Decision**: 沿用現有 FastAPI 專案結構，僅新增 `system.py` 路由檔案，其餘皆為現有檔案的修改。

## Complexity Tracking

> 無 Constitution 違規，不需記錄。
