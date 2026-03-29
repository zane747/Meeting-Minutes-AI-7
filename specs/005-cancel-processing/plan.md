# Implementation Plan: 會議處理中止功能

**Branch**: `005-cancel-processing` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-cancel-processing/spec.md`

## Summary

在會議詳情頁的「處理中」畫面新增中止按鈕，透過資料庫狀態標記實現優雅中止（graceful cancellation）。背景任務在每個處理步驟之間檢查取消標記，偵測到後停止後續處理並釋放資源。已取消的會議可透過既有的重試機制重新處理。

## Technical Context

**Language/Version**: Python 3.11 + FastAPI
**Primary Dependencies**: FastAPI, SQLAlchemy (aiosqlite), Jinja2, PyTorch (CUDA)
**Storage**: SQLite (aiosqlite) — 不新增資料表，僅修改既有 MeetingStatus enum
**Testing**: pytest
**Target Platform**: Windows 11 (本地開發)
**Project Type**: Web service (FastAPI + Jinja2 SSR)
**Performance Goals**: 中止回饋 < 3 秒
**Constraints**: 不強制殺掉正在進行的 AI 運算，以步驟間檢查點實現優雅中止
**Scale/Scope**: 單一使用者本地部署

## Constitution Check

*GATE: Constitution 為未填寫的模板，無具體 gates。直接通過。*

## Project Structure

### Documentation (this feature)

```text
specs/005-cancel-processing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (by /speckit.tasks)
```

### Source Code (repository root)

```text
app/
├── api/routes/
│   └── meetings.py        ← 新增 POST /{meeting_id}/cancel API 端點
├── models/
│   └── database_models.py ← MeetingStatus enum 新增 CANCELLED 值
├── services/
│   └── meeting_processor.py ← 每步驟間新增取消檢查點
├── templates/
│   ├── meeting.html       ← 處理中畫面新增中止按鈕 + cancelled 狀態畫面
│   └── history.html       ← 歷史紀錄顯示 cancelled 狀態標籤
```

**Structure Decision**: 完全在既有檔案中修改，不新增檔案。改動集中在 4 個既有檔案。
