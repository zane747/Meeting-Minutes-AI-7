# Feature Specification: GPU/CPU 工作負載分工最佳化

**Feature Branch**: `002-gpu-cpu-workload-split`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "Whisper 使用 GPU 加速轉錄，Ollama 使用 CPU 推論摘要，消除 VRAM 搶佔與模型反覆載入開銷"

## Clarifications

### Session 2026-03-26

- Q: 說話者辨識（Diarization/pyannote）應分配到 GPU 還是 CPU？ → A: 維持 GPU 執行，與 Whisper 共用 GPU lock
- Q: Ollama CPU 模式是否可設定？ → A: 可設定，預設 CPU（新增 `.env` 參數 `OLLAMA_GPU=false`，預設關閉）

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 本地模式處理速度提升 (Priority: P1)

使用者上傳音檔並選擇本地模式處理時，系統自動將語音轉錄工作分配給 GPU、將摘要生成工作分配給 CPU（預設），無需使用者手動介入。整體處理時間相較於目前的序列式 GPU 搶佔模式明顯縮短。

**Why this priority**: 這是功能的核心價值——消除 VRAM 搶佔導致的模型反覆載入/卸載開銷，直接影響使用者等待時間。

**Independent Test**: 上傳一段 5 分鐘音檔，使用本地模式處理，觀察處理時間與目前方案的差異。

**Acceptance Scenarios**:

1. **Given** 使用者上傳音檔並選擇本地模式, **When** 系統開始處理, **Then** 語音轉錄使用 GPU 執行，摘要生成預設使用 CPU 執行，無需反覆卸載/載入模型
2. **Given** 使用者上傳音檔, **When** 處理完成, **Then** 整體處理時間比現有方案（GPU 搶佔模式）更短
3. **Given** 系統正在處理音檔, **When** 使用者查看進度, **Then** 進度條正常顯示各階段狀態

---

### User Story 2 - 無 GPU 環境自動退回全 CPU 模式 (Priority: P2)

在沒有 GPU 的環境中，系統自動將所有工作（轉錄、辨識與摘要）都分配到 CPU 執行，不會出錯或中斷。

**Why this priority**: 確保系統在各種硬體環境下都能正常運作，提供向下相容性。

**Independent Test**: 在設定檔中將裝置設為 CPU 模式，上傳音檔處理，確認正常完成。

**Acceptance Scenarios**:

1. **Given** 系統偵測不到 GPU（或使用者手動設定為 CPU 模式）, **When** 處理音檔, **Then** 轉錄、辨識與摘要均在 CPU 上執行，功能正常
2. **Given** GPU 環境但 VRAM 不足導致 OOM, **When** 轉錄失敗, **Then** 系統自動降級至 CPU 模式完成處理

---

### User Story 3 - 處理過程中 GPU 記憶體穩定 (Priority: P2)

處理音檔時 GPU 記憶體不會因為模型反覆載入/卸載而出現劇烈波動，Whisper 與 Diarization 獨佔 GPU 期間不受 Ollama 干擾。

**Why this priority**: 穩定的記憶體使用避免 OOM 風險，提升系統可靠性。

**Independent Test**: 處理多個音檔，透過系統狀態頁面或 nvidia-smi 觀察 GPU 記憶體使用曲線是否平穩。

**Acceptance Scenarios**:

1. **Given** 本地模式處理音檔（OLLAMA_GPU=false）, **When** Whisper 或 Diarization 轉錄中, **Then** Ollama 不佔用任何 GPU 記憶體
2. **Given** 連續處理多個音檔, **When** 觀察 GPU 記憶體, **Then** 不出現因模型交替載入導致的記憶體尖峰

---

### User Story 4 - 使用者可設定 Ollama 使用 GPU (Priority: P3)

擁有大 VRAM 顯卡的使用者可透過 `.env` 設定 `OLLAMA_GPU=true`，讓 Ollama 也使用 GPU 推論以獲得更快的摘要生成速度。

**Why this priority**: 提供彈性，讓不同硬體配置的使用者都能取得最佳效能。

**Independent Test**: 設定 `OLLAMA_GPU=true`，上傳音檔處理，確認 Ollama 使用 GPU 推論。

**Acceptance Scenarios**:

1. **Given** 使用者設定 `OLLAMA_GPU=true`, **When** 摘要生成時, **Then** Ollama 使用 GPU 推論
2. **Given** 使用者未設定 `OLLAMA_GPU` 或設為 `false`, **When** 摘要生成時, **Then** Ollama 使用 CPU 推論

---

### Edge Cases

- 若 Ollama 服務未啟動或不可用，系統應僅完成轉錄並回傳不含摘要的結果
- 若 GPU 在 Whisper 轉錄過程中發生 OOM，系統應自動降級至較小模型或 CPU 模式（現有機制）
- 若 Diarization 在 GPU 上發生 OOM，系統應自動退回 CPU 重試（現有機制）
- 若使用者使用遠端模式（Gemini），此功能不影響遠端處理流程
- 若使用者設定 `OLLAMA_GPU=true` 但 VRAM 不足，Ollama 會自動部分 offload 到 CPU（Ollama 內建行為）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系統 MUST 在本地模式中將 Whisper 語音轉錄分配給 GPU 執行
- **FR-002**: 系統 MUST 在本地模式中將 Diarization（pyannote）分配給 GPU 執行，與 Whisper 共用 GPU lock
- **FR-003**: 系統 MUST 預設將 Ollama 摘要生成分配給 CPU 執行（透過 API 參數指定 `num_gpu: 0`）
- **FR-004**: 系統 MUST 提供 `OLLAMA_GPU` 設定參數（預設 `false`），設為 `true` 時 Ollama 使用 GPU 推論
- **FR-005**: 系統 MUST 在 `OLLAMA_GPU=false` 時，Whisper 轉錄前不再卸載 Ollama 模型
- **FR-006**: 系統 MUST 在無 GPU 環境中自動將所有工作分配至 CPU
- **FR-007**: 系統 MUST 保留現有的 OOM 自動降級機制（Whisper 模型降級順序、CPU fallback）
- **FR-008**: 系統 MUST 不影響遠端模式（Gemini Provider）的處理流程

### Key Entities

- **DeviceManager**: 管理 GPU/CPU 裝置偵測與分配策略
- **LocalWhisperProvider**: 語音轉錄服務，綁定 GPU
- **DiarizationService**: 說話者辨識服務，綁定 GPU（與 Whisper 共用 GPU lock）
- **OllamaService**: 摘要生成服務，預設 CPU，可透過 `OLLAMA_GPU` 切換至 GPU

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 本地模式處理 5 分鐘音檔的總時間比現有方案縮短（消除模型載入/卸載開銷）
- **SC-002**: 處理過程中 GPU 記憶體不出現因 Ollama 模型載入導致的使用尖峰（`OLLAMA_GPU=false` 時）
- **SC-003**: 無 GPU 環境下功能 100% 正常運作，無錯誤
- **SC-004**: 連續處理 3 個以上音檔不出現 OOM 或記憶體洩漏
- **SC-005**: `OLLAMA_GPU=true` 時 Ollama 確實使用 GPU 推論

## Assumptions

- 使用者的 GPU 為消費級顯卡（如 RTX 4050, 6GB VRAM），VRAM 有限
- Ollama 已安裝並使用較小的模型（如 gemma2:2b），CPU 推論速度在可接受範圍內
- Whisper 與 Diarization 從 GPU 加速獲得的效能提升遠大於 Ollama 從 GPU 加速獲得的效能提升
- 現有的 GPU 推論排隊鎖（asyncio.Lock）機制維持不變，確保同時只有一個 Whisper/Diarization 任務使用 GPU
- 遠端模式（Gemini Provider）不受此變更影響
