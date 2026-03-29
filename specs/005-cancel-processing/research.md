# Research: 會議處理中止功能

## 1. 優雅中止的實作方式

**Decision**: 使用資料庫狀態標記（polling-based cancellation）

**Rationale**: 背景任務（BackgroundTasks）在 FastAPI 中無法被直接中斷。最可靠的方式是在資料庫中標記狀態為 cancelled，讓背景任務在每個處理步驟之間主動檢查。這與現有的 `_update_progress()` 函式模式一致。

**Alternatives considered**:
- asyncio.Task.cancel() — 需要持有 task reference，且 FastAPI BackgroundTasks 不暴露此介面
- 全域 Event/Flag — 需要管理 per-meeting 的 flag，複雜度高於資料庫方案
- Redis pub/sub — 引入新依賴，不符合專案「不新增外部依賴」的原則

## 2. 重試功能複用

**Decision**: 擴展既有的 `retry_processing()` API，讓 cancelled 狀態也允許重試

**Rationale**: 現有 retry API 已處理了重設狀態、重新選擇 provider、啟動背景任務等邏輯。只需將狀態檢查從 `status == FAILED` 放寬為 `status in (FAILED, CANCELLED)` 即可。

**Alternatives considered**:
- 新建獨立的 resume API — 功能重複，增加維護成本

## 3. 前端輪詢整合

**Decision**: 複用既有的 HTMX polling 機制（每 2 秒查詢 /status），在 JavaScript 中新增 cancelled 狀態處理

**Rationale**: meeting.html 已有 polling 邏輯監聽 status 變化。只需在現有的 `htmx:afterRequest` handler 中加入 `cancelled` 判斷即可。

**Alternatives considered**:
- WebSocket — 過度設計，現有 polling 已足夠
