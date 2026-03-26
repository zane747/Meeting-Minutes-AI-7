# Feature Specification: Ollama GPU 加速與模型升級

**Feature Branch**: `003-ollama-gpu-boost`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "兩個都做 — Ollama 摘要改用更強模型 + Whisper 完成後自動將 Ollama 切到 GPU 執行"

## Clarifications

### Session 2026-03-26

- Q: `OLLAMA_GPU` 設定應改為何種策略？ → A: 改為三態：`auto`（預設，自動偵測 GPU 可用性）/ `true`（強制 GPU）/ `false`（強制 CPU）
- Q: 重新生成摘要時舊資料如何處理？ → A: 完全取代——刪除舊的摘要、待辦事項、語意分析，寫入新結果

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Whisper 完成後 Ollama 自動切換 GPU 執行 (Priority: P1)

使用者上傳音檔進行本地模式處理時，系統先以 GPU 執行 Whisper 語音轉錄，完成後自動釋放 VRAM，接著讓 Ollama 在 GPU 上執行摘要生成，大幅縮短摘要等待時間。

**Why this priority**: 40 分鐘音檔的摘要在 CPU 上需要 3~5 分鐘，切到 GPU 後可快 5~10 倍，直接影響使用者體驗。

**Independent Test**: 上傳一段音檔，觀察 Whisper 轉錄完成後 Ollama 是否自動使用 GPU 執行摘要，並確認 VRAM 使用量變化。

**Acceptance Scenarios**:

1. **Given** 使用者上傳音檔並選擇本地模式，**When** Whisper 轉錄完成並釋放 GPU 記憶體後，**Then** Ollama 摘要自動使用 GPU 執行，VRAM 顯示 Ollama 模型已載入
2. **Given** Whisper 正在 GPU 上轉錄，**When** 同時有摘要請求，**Then** Ollama 摘要等待 Whisper 完成後才使用 GPU，不會同時搶佔 VRAM
3. **Given** GPU VRAM 不足以載入 Ollama 模型，**When** 系統偵測到 VRAM 不足，**Then** 自動退回 CPU 模式執行摘要，不會導致程式崩潰

---

### User Story 2 - 使用者可設定 Ollama 使用更強模型 (Priority: P1)

使用者可在設定中切換 Ollama 使用的 LLM 模型（如從 gemma2:2b 升級到 gemma2 9B），以獲得更高品質的摘要結果。系統同時支援設定 CPU 執行緒數，充分利用多核心 CPU。

**Why this priority**: gemma2:2b 的摘要品質不佳（JSON 格式不完整、內容簡略），升級到 9B 模型可大幅改善品質，且使用者的 16 核 CPU 跑得動。

**Independent Test**: 修改設定檔中的模型名稱和執行緒數，重啟服務後觸發摘要，確認使用新模型且 CPU 使用率提升。

**Acceptance Scenarios**:

1. **Given** 使用者在設定中指定 Ollama 模型為 gemma2:latest，**When** 觸發摘要生成，**Then** 系統使用 gemma2:latest 模型產生摘要
2. **Given** 使用者設定 CPU 執行緒數為 16，**When** Ollama 在 CPU 模式下執行，**Then** CPU 使用率明顯提升，摘要速度加快
3. **Given** 使用者設定的模型尚未下載，**When** 觸發摘要生成，**Then** 系統回傳明確的錯誤訊息提示使用者先下載模型

---

### User Story 3 - 使用者可手動觸發重新生成摘要 (Priority: P2)

對已有逐字稿但摘要品質不佳的會議紀錄，使用者可手動觸發 Ollama 重新生成摘要，此時 Ollama 直接使用 GPU（因為 Whisper 不在運行）。

**Why this priority**: 允許使用者在升級模型或調整設定後，對舊紀錄重新生成更高品質的摘要。

**Independent Test**: 選擇一筆已完成的會議紀錄，點擊重新生成摘要，確認使用 GPU 且結果更新。

**Acceptance Scenarios**:

1. **Given** 一筆已有逐字稿的會議紀錄且 GPU 閒置，**When** 使用者觸發重新生成摘要，**Then** Ollama 使用 GPU 執行，摘要在合理時間內完成
2. **Given** 一筆已有摘要和待辦事項的會議紀錄，**When** 使用者觸發重新生成摘要，**Then** 舊的摘要、待辦事項、語意分析被刪除，新結果完全取代
3. **Given** 重新生成摘要期間，**When** 另一位使用者上傳新音檔，**Then** 新音檔的 Whisper 轉錄排隊等待 GPU 資源，不會互相衝突

---

### Edge Cases

- Whisper 轉錄異常中斷時，GPU 記憶體是否正確釋放，不影響後續 Ollama 使用 GPU？
- VRAM 剛好不夠載入 Ollama 模型（如 Whisper 未完全釋放）時，是否能安全退回 CPU？
- 設定了不存在的 Ollama 模型名稱時，是否有明確的錯誤提示？
- 超長逐字稿超過模型 context window 限制時，是否自動截斷並提示使用者？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `OLLAMA_GPU` 設定必須支援三態：`auto`（預設，自動偵測 GPU 可用性）、`true`（強制 GPU）、`false`（強制 CPU）。`auto` 模式下，Whisper 轉錄完成並釋放 GPU 記憶體後，自動將 Ollama 摘要切換至 GPU 執行
- **FR-002**: 系統必須支援設定 Ollama 使用的 LLM 模型名稱，允許使用者選擇不同大小的模型
- **FR-003**: 系統必須支援設定 CPU 執行緒數，讓 Ollama 在 CPU 模式下充分利用多核心
- **FR-004**: 系統必須在 GPU VRAM 不足時自動退回 CPU 模式執行 Ollama 摘要
- **FR-005**: 系統必須確保 Whisper 和 Ollama 不同時佔用 GPU，透過排隊機制避免 VRAM 衝突
- **FR-006**: 系統必須在逐字稿超過模型 context window 限制時自動截斷，並記錄警告
- **FR-007**: 系統必須提供足夠的超時時間，確保長逐字稿的摘要不會因超時而失敗
- **FR-008**: 手動觸發重新生成摘要時，若 GPU 閒置，系統必須使用 GPU 執行
- **FR-009**: 重新生成摘要時，系統必須先刪除該會議的舊摘要、待辦事項及語意分析資料，再寫入新結果（完全取代，非追加）

### Key Entities

- **Ollama 設定**: 模型名稱、context window 大小、CPU 執行緒數、GPU 模式（auto/true/false）
- **GPU 資源鎖**: 確保 Whisper 和 Ollama 不同時佔用 GPU 的排隊機制
- **摘要結果**: 標題建議、會議摘要、待辦事項、語意分析

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 40 分鐘音檔的 Ollama 摘要生成時間從 3~5 分鐘縮短至 1 分鐘以內（GPU 模式）
- **SC-002**: 摘要品質提升：9B 模型產生的摘要包含完整的 JSON 結構（標題、摘要、待辦事項、語意分析均有值）
- **SC-003**: GPU 與 CPU 之間的切換過程不會導致任何記憶體洩漏或程式崩潰
- **SC-004**: 使用者修改設定後重啟服務即可生效，無需額外操作
- **SC-005**: CPU 模式下設定 16 執行緒後，摘要速度相比預設提升至少 3 倍

## Assumptions

- 使用者的 GPU 為 NVIDIA RTX 4050 Laptop（6GB VRAM），Whisper medium 模型佔用約 4.5GB，釋放後足以載入 gemma2 9B（約 5GB）
- Whisper 和 Ollama 的 GPU 使用為先後順序（序列執行），不需要同時並行
- 使用者已安裝 Ollama 並下載所需模型
- 系統已有 GPU 推論排隊鎖機制（`_gpu_lock`），可在此基礎上擴展
- CPU 模式仍作為 fallback 保留，確保 GPU 不可用時系統仍能運作
