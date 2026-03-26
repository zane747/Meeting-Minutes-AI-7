# Tasks: GPU/CPU 工作負載分工最佳化

**Input**: Design documents from `/specs/002-gpu-cpu-workload-split/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

**Tests**: 未明確要求，不生成測試任務。以手動驗證（nvidia-smi + 功能測試）為主。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 新增設定參數，為後續服務層變更做準備

- [x] T001 新增 `OLLAMA_GPU` 設定參數（預設 `false`）至 app/config.py
- [x] T002 [P] 新增 `OLLAMA_GPU=false` 至 .env 和 .env.example

**Checkpoint**: 設定參數就位，應用可正常啟動

---

## Phase 2: User Story 1 - 本地模式處理速度提升 (Priority: P1) 🎯 MVP

**Goal**: Ollama 預設走 CPU（num_gpu=0），Whisper 轉錄前不再卸載 Ollama，消除模型 swap 開銷

**Independent Test**: 上傳音檔使用本地模式，確認處理正常完成且 Ollama 不佔 GPU（nvidia-smi）

### Implementation for User Story 1

- [x] T003 [US1] 修改 Ollama API 呼叫，根據 `OLLAMA_GPU` 設定加入 `num_gpu: 0` 至 app/services/ollama_service.py
- [x] T004 [US1] 修改 Whisper 轉錄前的 `unload_ollama()` 邏輯，`OLLAMA_GPU=false` 時跳過卸載，在 app/services/providers/local_whisper_provider.py

**Checkpoint**: 本地模式處理正常，Ollama 走 CPU，無模型 swap 開銷

---

## Phase 3: User Story 2 - 無 GPU 環境自動退回全 CPU 模式 (Priority: P2)

**Goal**: 確保無 GPU 時所有元件（含 Ollama num_gpu 邏輯）都正常走 CPU

**Independent Test**: 設定 `DEVICE=cpu`，上傳音檔處理，確認正常完成

### Implementation for User Story 2

- [x] T005 [US2] 確認 `DEVICE=cpu` 時 Ollama 的 `num_gpu` 參數行為正確（不傳 num_gpu 或傳 0），驗證 app/services/ollama_service.py 邏輯
- [x] T006 [US2] 確認 OOM fallback 路徑中 Ollama 仍正常走 CPU，驗證 app/services/providers/local_whisper_provider.py 邏輯

**Checkpoint**: 純 CPU 模式下功能 100% 正常

---

## Phase 4: User Story 3 - GPU 記憶體穩定 (Priority: P2)

**Goal**: 確保處理過程中 GPU 記憶體無異常尖峰

**Independent Test**: 連續處理 3 個音檔，觀察 nvidia-smi GPU 記憶體使用

### Implementation for User Story 3

- [x] T007 [US3] 驗證連續處理多檔時 GPU 記憶體穩定，無洩漏（手動測試 + 檢查 release_gpu_memory 呼叫路徑）

**Checkpoint**: 連續處理不出現 OOM 或記憶體持續上升

---

## Phase 5: User Story 4 - OLLAMA_GPU 可設定 (Priority: P3)

**Goal**: `OLLAMA_GPU=true` 時 Ollama 使用 GPU，且 Whisper 前正確卸載 Ollama

**Independent Test**: 設定 `OLLAMA_GPU=true`，上傳音檔處理，確認 Ollama 使用 GPU

### Implementation for User Story 4

- [x] T008 [US4] 驗證 `OLLAMA_GPU=true` 時 Ollama 不傳 `num_gpu`（使用預設 GPU），在 app/services/ollama_service.py
- [x] T009 [US4] 驗證 `OLLAMA_GPU=true` 時 Whisper 轉錄前仍執行 `unload_ollama()`，在 app/services/providers/local_whisper_provider.py

**Checkpoint**: OLLAMA_GPU=true/false 兩種模式均正常運作

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 文件更新與最終驗證

- [x] T010 [P] 更新 .env.example 中 OLLAMA_GPU 的說明註解
- [x] T011 執行 quickstart.md 驗證流程，確認所有場景通過

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 無依賴，立即開始
- **User Story 1 (Phase 2)**: 依賴 Phase 1（需要 OLLAMA_GPU 設定）
- **User Story 2 (Phase 3)**: 依賴 Phase 2（需要 num_gpu 邏輯已實作）
- **User Story 3 (Phase 4)**: 依賴 Phase 2（需要新邏輯已實作才能驗證）
- **User Story 4 (Phase 5)**: 依賴 Phase 2（需要條件邏輯已實作）
- **Polish (Phase 6)**: 依賴所有 User Story 完成

### User Story Dependencies

- **US1 (P1)**: 核心變更，其他 story 都依賴它
- **US2 (P2)**: 可在 US1 完成後獨立驗證
- **US3 (P2)**: 可在 US1 完成後獨立驗證，與 US2 平行
- **US4 (P3)**: 可在 US1 完成後獨立驗證，與 US2/US3 平行

### Parallel Opportunities

- T001 和 T002 可平行（不同檔案）
- US2、US3、US4 在 US1 完成後可平行驗證
- T010 可與其他 Phase 6 任務平行

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup（T001, T002）
2. Complete Phase 2: User Story 1（T003, T004）
3. **STOP and VALIDATE**: 上傳音檔測試，nvidia-smi 確認 Ollama 不佔 GPU
4. 若 MVP 通過，已實現核心價值

### Incremental Delivery

1. Setup + US1 → 核心功能可用（MVP）
2. US2 → 純 CPU 相容性確認
3. US3 → 記憶體穩定性確認
4. US4 → 大 VRAM 使用者彈性

---

## Notes

- 此功能變更範圍極小（3 個原始碼檔案 + 設定檔）
- 無資料庫 schema 變更
- 主要風險在於 Ollama `num_gpu: 0` 的行為是否符合預期，US1 完成後應立即手動驗證
- Diarization 不需變更（維持 GPU，已確認）
