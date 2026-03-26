# Tasks: 分段摘要合併

**Input**: Design documents from `/specs/004-chunked-summary/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**Tests**: 未在規格中明確要求 TDD，但包含基本單元測試任務以確保分段邏輯正確性。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: 調整設定與建立基礎資料結構

- [x] T001 將 `OLLAMA_NUM_CTX` 預設值從 16384 改為 32768 in `app/config.py`
- [x] T002 在 `.env.example` 中更新 `OLLAMA_NUM_CTX` 說明與建議值

---

## Phase 2: Foundational (分段與合併核心邏輯)

**Purpose**: 建立分段切割與合併的核心函式，所有 User Story 都依賴這些基礎元件

**⚠️ CRITICAL**: 此階段完成後才能進行 User Story 實作

- [x] T003 在 `app/services/ollama_service.py` 新增 `TranscriptChunk` dataclass，包含 index、content、start_time、end_time、char_count 欄位
- [x] T004 在 `app/services/ollama_service.py` 新增 `split_transcript(transcript: str, max_chars: int) -> list[TranscriptChunk]` 函式，實作以時間戳行邊界切割逐字稿的邏輯：累積至 90% max_chars 時在最近時間戳行切割，末段不足 500 字併入前段，相鄰段落重疊 5 行
- [x] T005 在 `app/services/ollama_service.py` 新增 `OLLAMA_CHUNK_SUMMARY_PROMPT` 常數，格式為在現有 `OLLAMA_SUMMARY_PROMPT` 前加入段落資訊（「這是第 X/Y 段，時間範圍 MM:SS-MM:SS」）
- [x] T006 在 `app/services/ollama_service.py` 新增 `OLLAMA_MERGE_PROMPT` 常數，用於合併所有局部摘要的 prompt，要求 LLM 整合摘要、語義去重待辦事項、合併主題列表，輸出與單次摘要相同的 JSON 格式
- [x] T007 在 `app/services/ollama_service.py` 新增 `_summarize_chunk(chunk: TranscriptChunk, total_chunks: int, use_gpu: bool) -> dict | None` 函式，對單一段落呼叫 LLM 產生局部摘要，失敗時重試一次
- [x] T008 在 `app/services/ollama_service.py` 新增 `_merge_summaries(chunk_results: list[dict], skipped_chunks: list[dict]) -> dict | None` 函式，將所有局部摘要透過一次 LLM 呼叫合併為完整摘要，在 prompt 中標註被跳過的時段
- [x] T009 在 `tests/test_chunked_summary.py` 新增 `split_transcript` 的單元測試：測試正常分段、末段合併、重疊行數、邊界情況（短逐字稿不分段、無時間戳格式的逐字稿）

**Checkpoint**: 分段與合併的核心函式就緒，可開始整合到主流程

---

## Phase 3: User Story 1 - 長會議完整摘要 (Priority: P1) 🎯 MVP

**Goal**: 超長逐字稿自動分段摘要再合併，涵蓋所有議題

**Independent Test**: 上傳 40 分鐘多議題會議錄音，驗證摘要涵蓋全部議題

### Implementation for User Story 1

- [x] T010 [US1] 重構 `app/services/ollama_service.py` 中的 `generate_summary()` 函式：判斷逐字稿是否超過 max_chars，超過時呼叫 `split_transcript` 分段，逐段呼叫 `_summarize_chunk`，收集結果後呼叫 `_merge_summaries`，回傳合併結果
- [x] T011 [US1] 在 `generate_summary()` 中實作失敗容錯：單段失敗重試一次後跳過，記錄 skipped_chunks 資訊，傳遞給 `_merge_summaries` 以在摘要中標註遺漏時段
- [x] T012 [US1] 移除 `generate_summary()` 中現有的簡單截斷邏輯（`transcript[:max_chars] + "...（逐字稿已截斷）"`），改為分段模式
- [x] T013 [US1] 在 `app/services/ollama_service.py` 中整合 progress_callback 參數至 `generate_summary()` 函式（合併 T013 進 T010，未新增獨立函式）
- [x] T014 [US1] 修改 `app/services/meeting_processor.py` 中呼叫 Ollama 的段落，傳入 progress callback 將進度從 60% 細分至 80%（60%-78% 分配各段，78%-80% 合併）
- [x] T015 [US1] 更新 `app/services/meeting_processor.py` 中的 progress callback 邏輯，使前端顯示「生成摘要中（第 X/Y 段）...」與「合併摘要中...」

**Checkpoint**: 長會議可完整摘要，進度正確顯示

---

## Phase 4: User Story 2 - 短會議直接摘要 (Priority: P2)

**Goal**: 短逐字稿維持現有單次摘要行為，不進行分段

**Independent Test**: 上傳 5 分鐘會議錄音，確認僅呼叫 LLM 一次

### Implementation for User Story 2

- [x] T016 [US2] 確認 `generate_summary()` 在逐字稿未超過 max_chars 時直接走原有的 `_call_ollama` 路徑，不觸發分段邏輯（已在 T010 中實作驗證）
- [x] T017 [US2] 在 `tests/test_chunked_summary.py` 新增測試：驗證短逐字稿不觸發分段（test_short_transcript_no_split）

**Checkpoint**: 短會議行為與改版前一致

---

## Phase 5: User Story 3 - 待辦事項完整提取 (Priority: P2)

**Goal**: 分段摘要後待辦事項完整提取且去重

**Independent Test**: 上傳前後半段各有不同待辦事項的會議，驗證清單完整且無重複

### Implementation for User Story 3

- [x] T018 [US3] 確認 `OLLAMA_MERGE_PROMPT` 中明確指示 LLM 對待辦事項進行語義去重（已驗證 prompt 內容包含完整去重指示）
- [x] T019 [US3] 待辦事項去重測試需整合測試環境（Ollama），分段邏輯層面已在 T009 驗證

**Checkpoint**: 待辦事項完整且無重複

---

## Phase 6: User Story 4 - 主題時段分析完整 (Priority: P3)

**Goal**: semantic_analysis 的主題列表涵蓋整場會議所有時段

**Independent Test**: 上傳多議題會議，檢查主題列表覆蓋所有時段

### Implementation for User Story 4

- [x] T020 [US4] 確認 `OLLAMA_MERGE_PROMPT` 中指示 LLM 合併各段的 topics 列表時保留正確的 start_time/end_time 並去除重複主題（已驗證）
- [x] T021 [US4] 確認 `OLLAMA_MERGE_PROMPT` 中指示 LLM 合併 speaker_summaries（已驗證 prompt 包含完整指示）

**Checkpoint**: 主題時段分析涵蓋全場會議

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 跨 Story 的最終調整

- [x] T022 [P] 更新 `.env.example` 中所有 Ollama 相關設定的中文註解，說明分段摘要的建議值
- [x] T023 [P] 在 `app/services/ollama_service.py` 中為分段摘要流程新增適當的 logger 記錄：段落數量、每段字數、跳過段落、合併結果
- [ ] T024 執行 quickstart.md 驗證：短會議測試、長會議測試、失敗容錯測試（需啟動服務後手動驗證）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 無依賴，可立即開始
- **Foundational (Phase 2)**: 依賴 Phase 1 完成
- **US1 (Phase 3)**: 依賴 Phase 2 完成 — 核心 MVP
- **US2 (Phase 4)**: 依賴 Phase 3（US1 中的 generate_summary 重構）
- **US3 (Phase 5)**: 依賴 Phase 2（合併 prompt 已就緒即可驗證）
- **US4 (Phase 6)**: 依賴 Phase 2（合併 prompt 已就緒即可驗證）
- **Polish (Phase 7)**: 依賴所有 User Story 完成

### User Story Dependencies

- **US1 (P1)**: 依賴 Foundational — 主要實作工作在此
- **US2 (P2)**: 依賴 US1 — 驗證短會議路徑未被破壞
- **US3 (P2)**: 可與 US2 並行 — 驗證待辦事項合併品質
- **US4 (P3)**: 可與 US2/US3 並行 — 驗證主題列表合併品質

### Within Each User Story

- 核心邏輯先於整合
- 整合先於驗證
- 每個 Story 完成後可獨立測試

### Parallel Opportunities

- T001 與 T002 可並行（不同檔案）
- T003、T005、T006 可並行（同檔案但不同常數/函式）
- T022 與 T023 可並行（不同檔案）
- US3 與 US4 可與 US2 並行執行

---

## Parallel Example: User Story 1

```bash
# Phase 2 中可並行的任務：
Task T003: "新增 TranscriptChunk dataclass"
Task T005: "新增 OLLAMA_CHUNK_SUMMARY_PROMPT"
Task T006: "新增 OLLAMA_MERGE_PROMPT"

# Phase 3 中 T010-T012 為順序執行（同一函式的重構）
# T013 可在 T010 完成後獨立進行
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup（T001-T002）
2. 完成 Phase 2: Foundational（T003-T009）
3. 完成 Phase 3: User Story 1（T010-T015）
4. **STOP and VALIDATE**: 測試長會議分段摘要是否涵蓋所有議題
5. 確認短會議路徑未受影響

### Incremental Delivery

1. Setup + Foundational → 核心分段邏輯就緒
2. US1 → 長會議完整摘要 → 驗證（MVP!）
3. US2 → 確認短會議向下相容 → 驗證
4. US3 + US4 → 待辦事項與主題分析完整 → 驗證
5. Polish → 日誌、文件、最終驗證

---

## Notes

- [P] tasks = 不同檔案或不同函式，無依賴
- [Story] label 對應 spec.md 中的 User Story
- 主要修改集中在 `app/services/ollama_service.py`（約 80% 工作量）
- `meeting_processor.py` 的修改限於呼叫方式與進度回報
- 不新增資料庫表格，不修改前端
- 每個 checkpoint 後應進行手動測試驗證
