# Implementation Plan: 分段摘要合併

**Branch**: `004-chunked-summary` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-chunked-summary/spec.md`

## Summary

解決長會議逐字稿因超出 LLM context window 而被截斷的問題。將逐字稿按時間戳行邊界分割成多段，各段分別呼叫 Ollama 產生局部摘要，最後透過一次 LLM 合併呼叫整合為完整的會議摘要、待辦清單與主題列表。短會議維持原有的單次摘要流程不變。

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: FastAPI, httpx, SQLAlchemy (aiosqlite), pydantic-settings, PyTorch (CUDA)
**Storage**: SQLite (aiosqlite) — 不新增資料表
**Testing**: pytest
**Target Platform**: Windows 11 本地部署
**Project Type**: Web service (FastAPI + HTMX 前端)
**Performance Goals**: 分段摘要總時間 ≤ 單次摘要 × (N+1)，N = 段落數
**Constraints**: RTX 4050 (6GB VRAM)，Ollama context window 32K tokens
**Scale/Scope**: 支援最長 2 小時會議（約 8-12 段）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution 為空模板（專案未定義原則），無 gate 需要檢查。通過。

**Post-design re-check**: 通過。設計未引入新框架或不必要的抽象層。

## Project Structure

### Documentation (this feature)

```text
specs/004-chunked-summary/
├── plan.md              # 本檔案
├── research.md          # Phase 0 研究結果
├── data-model.md        # 記憶體資料結構定義
├── quickstart.md        # 快速驗證指南
├── checklists/
│   └── requirements.md  # 規格品質檢查表
└── tasks.md             # Phase 2 任務清單（/speckit.tasks 產出）
```

### Source Code (repository root)

```text
app/
├── services/
│   ├── ollama_service.py      # 主要修改：新增分段、合併邏輯
│   └── meeting_processor.py   # 修改：整合分段流程、細分進度
├── config.py                  # 修改：OLLAMA_NUM_CTX 預設值調整
└── models/
    └── schemas.py             # 不修改

tests/
└── test_chunked_summary.py    # 新增：分段邏輯單元測試
```

**Structure Decision**: 本功能集中修改 `ollama_service.py`（新增分段與合併函式），並調整 `meeting_processor.py` 的呼叫流程與進度回報。不新增獨立模組，以降低複雜度。

## Complexity Tracking

無 constitution 違規，不需要複雜度追蹤。
