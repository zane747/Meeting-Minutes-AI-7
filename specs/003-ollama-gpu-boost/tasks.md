# Tasks: Ollama GPU 加速與模型升級

**Input**: Design documents from `/specs/003-ollama-gpu-boost/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Config 三態設定與基礎參數調整

- [x] T001 將 `OLLAMA_GPU` 從 `bool` 改為 `str = "auto"`，新增 `field_validator` 驗證 `auto`/`true`/`false`（不區分大小寫）in app/config.py
- [x] T002 [P] ~~確認~~ ✅ 已完成：`OLLAMA_NUM_THREAD: int = 0` 和 `OLLAMA_NUM_CTX: int = 16384` 已在 app/config.py 中定義
- [x] T003 [P] 將 `.env` 和 `.env.example` 的 `OLLAMA_GPU` 從 `false` 改為 `auto`（其他欄位已在本次對話更新）

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ollama Service 核心邏輯，所有 User Story 都依賴此階段

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 重構 `generate_summary()` 中的 `num_gpu` 邏輯：根據 `OLLAMA_GPU` 三態決定參數（`"false"` → `num_gpu: 0`、`"true"` → 省略、`"auto"` → 先發送不含 `num_gpu` 的請求嘗試 GPU，捕獲錯誤後以 `num_gpu: 0` 重試 CPU fallback）in app/services/ollama_service.py
- [x] T005 ~~確認~~ ✅ 已完成：逐字稿截斷保護邏輯已實作，依 `OLLAMA_NUM_CTX` 計算 `max_chars`，超過時截斷並記錄警告 in app/services/ollama_service.py
- [x] T006 ~~確認~~ ✅ 已完成：timeout 已設為 600 秒，`num_thread` 在 `OLLAMA_NUM_THREAD > 0` 時正確傳遞 in app/services/ollama_service.py
- [x] T007 在 `generate_summary()` 的日誌中加入 GPU/CPU 模式資訊，方便使用者確認執行模式 in app/services/ollama_service.py

**Checkpoint**: Ollama Service 支援三態 GPU 設定，可獨立測試 `auto`/`true`/`false` 模式

---

## Phase 3: User Story 1 - Whisper 完成後 Ollama 自動切換 GPU (Priority: P1) 🎯 MVP

**Goal**: 上傳音檔後，Whisper 轉錄完成釋放 VRAM，Ollama 自動以 GPU 執行摘要

**Independent Test**: 上傳音檔，用 `nvidia-smi` 觀察 Whisper 結束後 VRAM 釋放，Ollama 載入 GPU 模型開始摘要

### Implementation for User Story 1

- [x] T008 [US1] 將 `_gpu_lock` 從 `meeting_processor.py` 移至 `DeviceManager`，新增 `get_gpu_lock()` 類別方法，讓所有需要 GPU 的模組共用同一把 lock in app/services/device_manager.py
- [x] T009 [US1] 修改 `process_meeting()` 改用 `DeviceManager.get_gpu_lock()`，並在 Whisper 完成釋放 VRAM 後，若 `OLLAMA_GPU` 為 `auto` 或 `true`，Ollama 摘要也在 GPU lock 內執行 in app/services/meeting_processor.py
- [x] T010 [US1] 修改 `LocalWhisperProvider.process()` 中呼叫 `ollama_service.generate_summary()` 的邏輯：傳遞 GPU 模式資訊，確保在 GPU lock 內正確執行 in app/services/providers/local_whisper_provider.py
- [x] T011 [US1] 在 `DeviceManager` 中新增 `is_gpu_available()` 輔助方法，回傳目前 GPU 是否閒置（有助於日誌和決策）in app/services/device_manager.py
- [x] T012 [US1] 手動驗證：上傳音檔，觀察終端日誌顯示 Whisper → GPU 釋放 → Ollama GPU 摘要的流程，`nvidia-smi` 確認 VRAM 變化；同時上傳兩檔確認排隊機制正常

**Checkpoint**: Whisper + Ollama 序列使用 GPU，無 VRAM 衝突，摘要速度明顯提升

---

## Phase 4: User Story 2 - 設定更強模型與 CPU 執行緒 (Priority: P1)

**Goal**: 使用者可設定 Ollama 使用 gemma2 9B 模型和 16 執行緒，獲得更好的摘要品質和速度

**Independent Test**: 修改 `.env` 中模型和執行緒設定，重啟服務，觸發摘要確認使用新模型

### Implementation for User Story 2

- [x] T013 [P] [US2] 在 `ollama_service.is_available()` 中增加模型存在性檢查：呼叫 `/api/tags` 確認設定的模型已下載，否則記錄警告 in app/services/ollama_service.py
- [x] T014 [US2] 在 `generate_summary()` 日誌中加入模型名稱和執行緒數資訊 in app/services/ollama_service.py
- [x] T015 [US2] 手動驗證：分別用 `gemma2:2b` 和 `gemma2:latest` 測試摘要品質，確認 JSON 結構完整性；修改 `OLLAMA_NUM_THREAD=16` 確認 CPU 使用率提升

**Checkpoint**: 支援不同模型和執行緒設定，摘要品質和速度可調整

---

## Phase 5: User Story 3 - 手動重新生成摘要 (Priority: P2)

**Goal**: 對已有逐字稿的會議紀錄重新生成摘要，完全取代舊資料，自動使用 GPU

**Independent Test**: 選擇一筆已完成的會議紀錄，觸發重新生成，確認舊資料被刪除、新結果寫入

### Implementation for User Story 3

- [x] T016 [US3] 修改 `/summarize` 端點：在生成新摘要前，先刪除該會議的舊 ActionItem 和 Topic（使用 SQLAlchemy 批次刪除）in app/api/routes/meetings.py
- [x] T017 [US3] 修改 `/summarize` 端點：在 `generate_summary()` 呼叫中使用 `DeviceManager.get_gpu_lock()`（`auto`/`true` 模式需 GPU lock，CPU 模式不需要）in app/api/routes/meetings.py
- [x] T018 [US3] 修改 `/summarize` 端點：儲存 semantic_analysis 結果（Topics），與 `meeting_processor.py` 中的邏輯一致 in app/api/routes/meetings.py
- [ ] T019 [US3] 手動驗證：對一筆已有摘要的會議觸發重新生成，確認舊 ActionItem/Topic 被刪除、新結果寫入、GPU 模式正確

**Checkpoint**: 重新生成摘要完全取代舊資料，GPU 模式正確

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 最終驗證和文件更新

- [x] T020 [P] 更新 `.env.example` 的註解說明，確保三態 GPU 設定和執行緒說明清楚
- [x] T021 [P] 清理測試檔案 `test_ollama_debug.py`（開發過程中的除錯用腳本）
- [x] T022 執行 quickstart.md 完整驗證流程：上傳 40 分鐘音檔，確認端到端 GPU 自動切換正常
- [x] T023 確認所有 Success Criteria 達成：GPU 摘要完成、JSON 完整、無記憶體洩漏、GPU 自動切換正常

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on T001 (config 三態) completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion
- **User Story 2 (Phase 4)**: Depends on Phase 2 completion, can run in parallel with US1
- **User Story 3 (Phase 5)**: Depends on Phase 2 completion, can run in parallel with US1/US2
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: 核心 GPU 自動切換 — MVP 目標
- **User Story 2 (P1)**: 模型和執行緒設定 — 可與 US1 並行，但建議先完成 US1 以驗證 GPU 流程
- **User Story 3 (P2)**: 重新生成摘要 — 可獨立實作，依賴 Phase 2 的 `generate_summary()` 邏輯

### Within Each User Story

- Config 變更 before Service 邏輯
- Service 邏輯 before Endpoint 整合
- 整合完成 before 手動驗證

### Parallel Opportunities

- T003 可與 T001 並行（不同檔案）
- T013 可與 US1 的 T008-T011 並行（不同邏輯區塊）
- T016 和 T017 可並行（meetings.py 不同區塊，但建議循序以避免衝突）
- T020 和 T021 可並行（不同檔案）

---

## Parallel Example: Phase 1

```bash
# 三個 Setup tasks 可同時進行：
Task T001: "Config 三態設定 in app/config.py"
Task T003: "更新 .env 和 .env.example"  # T002 已完成
```

## Parallel Example: User Story 1 + User Story 2

```bash
# US1 和 US2 可部分並行（Phase 2 完成後）：
# Developer A (US1):
Task T008: "移動 _gpu_lock 至 DeviceManager"
Task T009: "修改 meeting_processor.py 使用共用 GPU lock"

# Developer B (US2):
Task T013: "ollama_service.py 模型存在性檢查"
Task T014: "ollama_service.py 日誌加入模型資訊"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup（T001, T003）
2. Complete Phase 2: Foundational（T004, T007）
3. Complete Phase 3: User Story 1（T008-T012）
4. **STOP and VALIDATE**: 上傳音檔測試 GPU 自動切換
5. 確認 VRAM 正確釋放和載入

### Incremental Delivery

1. Setup + Foundational → Config 和 Ollama Service 就緒
2. Add User Story 1 → GPU 自動切換可用 → **MVP!**
3. Add User Story 2 → 更強模型 + 更快速度
4. Add User Story 3 → 舊紀錄可重新生成
5. Polish → 清理 + 完整驗證

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- T002/T005/T006 已在本次對話中完成，標記為 ✅
- 手動驗證任務（T012, T015, T019, T022）需要實際上傳音檔測試
- GPU lock 架構決策：共用 `DeviceManager.get_gpu_lock()`，避免多把 lock 造成死鎖
- Commit after each task or logical group
