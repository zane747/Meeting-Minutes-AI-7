# Tasks: GPU 加速模型推論

**Input**: Design documents from `/specs/001-gpu-acceleration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/system-status-api.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: 確保 GPU 加速所需的基礎環境就緒

- [x] T001 更新 pyproject.toml 加入 CUDA 安裝說明註解與 torch 依賴版本備註 in pyproject.toml
- [x] T002 [P] 更新 .env.example 補充 DEVICE、WHISPER_MODEL 等 GPU 相關設定說明 in .env.example
- [x] T003 [P] 在 app/config.py 新增 WHISPER_MODEL_FALLBACK_ORDER 設定項（預設 `["medium", "small", "base", "tiny"]`） in app/config.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DeviceManager 核心增強 — 所有 User Story 都依賴此階段

**⚠️ CRITICAL**: 此階段必須完成後才能開始任何 User Story

- [x] T004 擴充 DeviceManager 新增 `_current_model_size` 和 `_last_fallback_reason` 屬性，以及 `get_status()` 方法回傳目前裝置狀態 in app/services/device_manager.py
- [x] T005 [P] 在 DeviceManager 新增 `get_vram_info()` 方法回傳 GPU VRAM 總量與已使用量 in app/services/device_manager.py
- [x] T006 在 DeviceManager 新增 `suggest_model_fallback(current_model, fallback_order)` 方法，回傳降級順序中的下一個可用模型 in app/services/device_manager.py
- [x] T007 在 MeetingProcessor 新增 `asyncio.Lock` 實作 GPU 推論排隊機制，確保同一時間只有一個音檔進行 GPU 推論 in app/services/meeting_processor.py

**Checkpoint**: DeviceManager 增強完成，排隊機制就緒 — User Story 實作可以開始

---

## Phase 3: User Story 1 — 語音轉文字處理加速 (Priority: P1) 🎯 MVP

**Goal**: Whisper 語音轉文字自動使用 GPU 加速，OOM 時自動降級至較小模型，最終退回 CPU

**Independent Test**: 上傳 10 分鐘會議錄音，確認 GPU 模式下處理時間比 CPU 減少 50% 以上；模擬 VRAM 不足時能自動降級完成處理

### Implementation for User Story 1

- [x] T008 [US1] 修改 LocalWhisperProvider.transcribe() 加入 OOM 捕捉迴圈：遇到 torch.cuda.OutOfMemoryError 時，依 WHISPER_MODEL_FALLBACK_ORDER 自動嘗試較小模型繼續 GPU 推論 in app/services/providers/local_whisper_provider.py
- [x] T009 [US1] 在 OOM 降級迴圈中，若所有 GPU 模型均 OOM，最終退回 CPU 模式載入使用者原始設定模型，並透過 DeviceManager 記錄降級原因 in app/services/providers/local_whisper_provider.py
- [x] T010 [US1] 確保每次 Whisper 推論完成後呼叫 DeviceManager 釋放 GPU 記憶體（torch.cuda.empty_cache + gc.collect） in app/services/providers/local_whisper_provider.py
- [x] T011 [US1] 在 LocalWhisperProvider 推論前呼叫 DeviceManager 卸載 Ollama 模型（若 CUDA + Ollama 啟用），避免 VRAM 衝突 in app/services/providers/local_whisper_provider.py
- [x] T012 [US1] 修改 MeetingProcessor 中呼叫 Whisper 的流程，包裹在 asyncio.Lock 內以實現排隊機制 in app/services/meeting_processor.py

**Checkpoint**: 語音轉文字 GPU 加速功能完整可用，含 OOM 自動降級與 CPU fallback

---

## Phase 4: User Story 2 — 說話者辨識處理加速 (Priority: P2)

**Goal**: pyannote 說話者辨識自動使用 GPU 加速，與 Whisper 共享排隊機制協調資源

**Independent Test**: 上傳多人對話錄音並啟用說話者辨識，確認使用 GPU 加速處理速度明顯提升

### Implementation for User Story 2

- [x] T013 [US2] 修改 DiarizationService 加入 OOM 捕捉：遇到 torch.cuda.OutOfMemoryError 時自動退回 CPU 模式完成辨識，並記錄降級原因 in app/services/diarization_service.py
- [x] T014 [US2] 確保 DiarizationService 推論完成後呼叫 DeviceManager 釋放 GPU 記憶體 in app/services/diarization_service.py
- [x] T015 [US2] 修改 MeetingProcessor 中呼叫 Diarization 的流程，與 Whisper 共用同一個 asyncio.Lock 確保不同時佔用 GPU in app/services/meeting_processor.py

**Checkpoint**: 說話者辨識 GPU 加速完成，與 Whisper 排隊機制整合正常

---

## Phase 5: User Story 3 — 處理狀態與效能透明度 (Priority: P3)

**Goal**: 提供系統狀態 API 端點，讓使用者查詢目前 GPU 狀態、模型資訊與降級紀錄

**Independent Test**: 啟動應用後呼叫 GET /api/system/status 確認回傳正確的 GPU 偵測資訊與模型狀態

### Implementation for User Story 3

- [x] T016 [P] [US3] 新增 SystemStatusResponse Pydantic schema 定義回傳結構（device、gpu_available、gpu_name、vram、whisper_model、active_model、fallback_reason 等欄位） in app/models/schemas.py
- [x] T017 [US3] 新增 GET /api/system/status 路由端點，呼叫 DeviceManager.get_status() 與 get_vram_info() 組裝回應 in app/api/routes/system.py
- [x] T018 [US3] 在 app/main.py 註冊 system router 至 FastAPI app in app/main.py

**Checkpoint**: 系統狀態 API 可用，前端或使用者可主動查詢 GPU 與模型狀態

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 跨 User Story 的改善與文件更新

- [x] T019 [P] 在 DeviceManager.initialize() 啟動時新增詳細 GPU 偵測 log（GPU 名稱、VRAM、驅動版本） in app/services/device_manager.py
- [x] T020 [P] 在 app/config.py 新增 DEVICE 設定選項驗證（auto/cpu/cuda），確保無效值時給出清楚錯誤訊息 in app/config.py
- [ ] T021 執行 quickstart.md 驗證流程：確認 CUDA 偵測、API 狀態端點、OOM 降級均按預期運作

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 無依賴 — 可立即開始
- **Foundational (Phase 2)**: 依賴 Phase 1 完成 — **阻擋所有 User Story**
- **User Story 1 (Phase 3)**: 依賴 Phase 2 完成
- **User Story 2 (Phase 4)**: 依賴 Phase 2 完成（可與 US1 並行）
- **User Story 3 (Phase 5)**: 依賴 Phase 2 完成（可與 US1/US2 並行）
- **Polish (Phase 6)**: 依賴所有 User Story 完成

### User Story Dependencies

- **US1 (P1)**: Phase 2 完成後即可開始 — 不依賴其他 Story
- **US2 (P2)**: Phase 2 完成後即可開始 — 與 US1 共用 Lock 但可獨立實作
- **US3 (P3)**: Phase 2 完成後即可開始 — 依賴 DeviceManager.get_status() (T004)

### Within Each User Story

- 模型/Schema 先於 Service
- Service 先於 API 端點
- 核心實作先於整合

### Parallel Opportunities

- Phase 1: T002、T003 可並行
- Phase 2: T005 可與 T004 並行（不同方法）
- Phase 3-5: US1、US2、US3 在 Phase 2 完成後可並行開始
- Phase 5: T016 可與其他 Story 並行（獨立 schema 檔案）

---

## Parallel Example: User Story 1

```bash
# T008, T009, T010, T011 在同一檔案，需依序執行
# T012 在不同檔案 (meeting_processor.py)，可與 T008-T011 並行
Task: "T008 修改 LocalWhisperProvider OOM 捕捉迴圈"
Task: "T012 修改 MeetingProcessor 排隊機制" (parallel - different file)
```

## Parallel Example: User Story 3

```bash
# T016 與 T017 在不同檔案，可並行
Task: "T016 新增 SystemStatusResponse schema in schemas.py"
Task: "T017 新增 system status 路由 in system.py" (parallel - different file)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational (CRITICAL)
3. 完成 Phase 3: User Story 1 — 語音轉文字 GPU 加速
4. **STOP and VALIDATE**: 測試 Whisper GPU 加速效果與 OOM 降級
5. 確認 10 分鐘音檔處理時間 < 3 分鐘

### Incremental Delivery

1. Setup + Foundational → 基礎就緒
2. US1 完成 → GPU 語音轉文字可用 (MVP!)
3. US2 完成 → 說話者辨識也享受 GPU 加速
4. US3 完成 → 系統狀態可查詢
5. Polish → 文件、驗證、log 完善

---

## Notes

- [P] tasks = 不同檔案，無依賴
- [Story] label 對應 spec.md 的 User Story
- 每個 User Story 可獨立完成與測試
- 每個 task 或邏輯群組完成後建議 commit
- 在任何 Checkpoint 停下來驗證 Story 獨立功能
