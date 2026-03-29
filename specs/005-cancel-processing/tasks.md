# Tasks: 會議處理中止功能

**Input**: Design documents from `/specs/005-cancel-processing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (資料模型變更)

**Purpose**: 新增 CANCELLED 狀態值，為所有後續任務奠基

- [x] T001 新增 CANCELLED 狀態到 MeetingStatus enum in app/models/database_models.py

---

## Phase 2: Foundational (背景任務取消檢查機制)

**Purpose**: 實作取消檢查點函式，所有 User Story 都依賴此機制

**⚠️ CRITICAL**: 必須先完成此階段，User Story 才能正確運作

- [x] T002 新增 `_check_cancelled()` 輔助函式 in app/services/meeting_processor.py — 從資料庫重新讀取 meeting status，若為 CANCELLED 則 log 並回傳 True
- [x] T003 在 `process_meeting()` 的每個處理步驟之間插入取消檢查點 in app/services/meeting_processor.py — 健康檢查後、diarization 後、AI 轉錄後、Ollama 摘要前、儲存結果前，共 5 個檢查點

**Checkpoint**: 取消檢查機制就緒，可開始 User Story 實作

---

## Phase 3: User Story 1 — 使用者中止正在處理的會議 (Priority: P1) 🎯 MVP

**Goal**: 使用者可在處理中頁面按下「中止」按鈕，透過確認對話框後取消 AI 處理

**Independent Test**: 上傳音檔 → 處理中按「中止」→ 確認 → 狀態變為 cancelled，終端機顯示偵測到取消

### Implementation for User Story 1

- [x] T004 [P] [US1] 新增 `POST /{meeting_id}/cancel` API 端點 in app/api/routes/meetings.py — 檢查 status == PROCESSING 後改為 CANCELLED，回傳 MessageResponse。加上學習備註說明此 API 在邏輯流向中的角色
- [x] T005 [P] [US1] 在 meeting.html 的「處理中」區塊新增「中止處理」按鈕 in app/templates/meeting.html — 紅色按鈕，放在進度條下方
- [x] T006 [US1] 新增中止按鈕的 JavaScript 邏輯 in app/templates/meeting.html — confirm() 對話框 → fetch POST /cancel → 按鈕變灰顯示「中止中...」。加上學習備註說明前端怎麼呼叫後端 API
- [x] T007 [US1] 在 htmx:afterRequest handler 新增 cancelled 狀態判斷 in app/templates/meeting.html — 偵測到 status === 'cancelled' 時重新載入頁面

**Checkpoint**: User Story 1 完成 — 使用者可中止處理中的會議

---

## Phase 4: User Story 2 — 已取消的會議可重新處理 (Priority: P2)

**Goal**: 已取消的會議顯示中止階段資訊，並提供重試按鈕

**Independent Test**: 中止一筆會議 → 頁面顯示「已取消」+ 中止階段 + 重試按鈕 → 按重試 → 重新開始處理

### Implementation for User Story 2

- [x] T008 [US2] 在 meeting.html 新增 cancelled 狀態區塊 in app/templates/meeting.html — 顯示「已取消」標題、progress_stage（中止時的處理階段）、遠端/本地模式重試按鈕（複用 failed 區塊的按鈕樣式）
- [x] T009 [US2] 修改 `retry_processing()` 放寬狀態檢查 in app/api/routes/meetings.py — 將 `status != FAILED` 改為 `status not in (FAILED, CANCELLED)`，讓已取消的會議也能重試

**Checkpoint**: User Story 2 完成 — 已取消的會議可查看中止階段並重試

---

## Phase 5: User Story 3 — 歷史紀錄中顯示取消狀態 (Priority: P3)

**Goal**: 歷史紀錄頁面正確顯示「已取消」狀態標籤

**Independent Test**: 取消一筆會議 → 回到歷史紀錄頁 → 該會議顯示橘色「已取消」標籤

### Implementation for User Story 3

- [x] T010 [US3] 在 history.html 新增 cancelled 狀態的標籤樣式 in app/templates/history.html — 橘色標籤，與 completed（綠色）、failed（紅色）、processing（藍色）做視覺區分

**Checkpoint**: User Story 3 完成 — 歷史紀錄顯示所有四種狀態

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 驗證整體功能、清理、學習備註

- [x] T011 執行 quickstart.md 的完整測試流程驗證（上傳→中止→確認→重試→歷史紀錄）
- [x] T012 確認 MeetingStatusResponse schema 能正確回傳 cancelled 狀態 in app/models/schemas.py — status: str 自動支援新的 enum 值，無需修改

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: 無依賴 — 立即開始
- **Phase 2 (Foundational)**: 依賴 Phase 1（需要 CANCELLED 狀態值）— **阻擋所有 User Story**
- **Phase 3 (US1)**: 依賴 Phase 2 — MVP 核心
- **Phase 4 (US2)**: 依賴 Phase 3（需要 cancel API 和 cancelled 狀態頁面）
- **Phase 5 (US3)**: 依賴 Phase 1（只需 CANCELLED 狀態值）— 可與 Phase 3 平行
- **Phase 6 (Polish)**: 依賴所有 User Story 完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 完成後即可開始 — 核心中止功能
- **US2 (P2)**: 依賴 US1（需要 cancel API 才能產生 cancelled 狀態的會議來重試）
- **US3 (P3)**: 可與 US1 平行（只需 Phase 1 的狀態值即可）

### Parallel Opportunities

- T004 和 T005 可平行（不同檔案）
- US1 和 US3 可平行（不同檔案、無相互依賴）

---

## Parallel Example: User Story 1

```bash
# 以下兩個任務可同時進行（不同檔案）：
Task T004: "新增 cancel API 端點 in meetings.py"
Task T005: "新增中止按鈕 in meeting.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. T001: 新增 CANCELLED 狀態
2. T002-T003: 建立取消檢查機制
3. T004-T007: 實作中止功能（前端+後端）
4. **STOP and VALIDATE**: 手動測試中止功能
5. 確認可用後再繼續 US2、US3

### Incremental Delivery

1. Phase 1+2 → 基礎就緒
2. + US1 → 中止功能可用（MVP!）
3. + US2 → 重試功能可用
4. + US3 → 歷史紀錄完整
5. 每一步都是獨立可用的增量

---

## Notes

- 所有程式碼修改都在既有檔案中，不新增檔案
- 加上學習備註（繁體中文）幫助理解邏輯流向
- Commit 建議：每完成一個 Phase 就 commit 一次
