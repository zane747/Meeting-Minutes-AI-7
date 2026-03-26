# Comprehensive Checklist: Ollama GPU 加速與模型升級

**Purpose**: 全面驗證 GPU 資源管理、Config 設定、API 行為變更的需求品質
**Created**: 2026-03-26
**Feature**: [spec.md](../spec.md)
**Depth**: 深入（全部涵蓋）
**Audience**: Author + Reviewer

## GPU 資源管理需求完整性

- [ ] CHK001 - `auto` 模式下「GPU 可用」的定義是否量化？（VRAM 閾值？CUDA 可用即算？）[Clarity, Spec §FR-001]
- [ ] CHK002 - GPU fallback 至 CPU 的觸發條件是否明確列舉？（OOM、HTTP 錯誤、timeout？）[Completeness, Spec §FR-004]
- [ ] CHK003 - GPU lock 的保護範圍是否完整涵蓋所有 GPU 消費者？（Whisper、Diarization、Ollama）[Coverage, Spec §FR-005]
- [ ] CHK004 - GPU lock 等待超時的需求是否定義？（永久等待 vs 超時放棄？）[Gap]
- [ ] CHK005 - Whisper 異常中斷後 GPU lock 是否保證釋放？是否有 lock 洩漏的防護需求？[Edge Case, Spec §Edge Cases]
- [ ] CHK006 - Ollama 在 GPU 模式下 VRAM 不足時的行為是否與 Whisper OOM fallback 一致？[Consistency]
- [ ] CHK007 - `auto` 模式下 GPU → CPU fallback 是否要記錄到使用者可見的介面（不只日誌）？[Gap]
- [ ] CHK008 - 多個 `/summarize` 請求同時到達時的排隊行為是否定義？[Coverage, Gap]
- [ ] CHK009 - GPU lock 跨越 Whisper 和 Ollama 的序列化是否會造成不必要的排隊？（CPU 模式 Ollama 不應被 lock 擋住）[Consistency, Spec §FR-005]
- [ ] CHK010 - Ollama `keep_alive: 0` 卸載後 VRAM 實際釋放的時間差是否考慮？[Edge Case]

## Config 三態設定需求品質

- [ ] CHK011 - `OLLAMA_GPU` 三態值（auto/true/false）的每種行為是否都有獨立的驗收場景？[Coverage, Spec §FR-001]
- [ ] CHK012 - 從舊版 `OLLAMA_GPU=true/false`（布林）升級到新版三態的向後相容性是否定義？[Gap]
- [ ] CHK013 - `OLLAMA_GPU=true` 但 GPU 不可用（無 NVIDIA 驅動）時的行為是否定義？[Edge Case, Gap]
- [ ] CHK014 - `OLLAMA_NUM_THREAD=0`（自動）與實際使用的執行緒數關係是否明確？[Clarity, Spec §FR-003]
- [ ] CHK015 - `OLLAMA_NUM_CTX` 設太小（如 1024）導致截斷後無法生成有意義摘要的需求是否考慮？[Edge Case, Gap]
- [ ] CHK016 - Config 驗證失敗時的錯誤訊息需求是否定義？（如 `OLLAMA_GPU=maybe`）[Completeness]
- [ ] CHK017 - `OLLAMA_NUM_THREAD` 設為負數或超過 CPU 核心數時的行為是否定義？[Edge Case, Gap]
- [ ] CHK018 - 是否需要在系統狀態 API 中暴露目前的 GPU 模式資訊？[Gap]

## Ollama 模型管理需求品質

- [ ] CHK019 - 模型不存在時的錯誤提示是否區分「Ollama 服務不可用」和「模型未下載」？[Clarity, Spec §US2 AS3]
- [ ] CHK020 - 模型名稱格式的驗證需求是否定義？（如 `gemma2:latest` vs `gemma2` vs 不合法名稱）[Gap]
- [ ] CHK021 - 切換模型是否需要重啟服務的需求是否明確？[Clarity, Spec §SC-004]
- [ ] CHK022 - 不同模型對 VRAM 的需求差異是否在需求中記錄？（2B vs 9B）[Completeness, Spec §Assumptions]
- [ ] CHK023 - 是否定義了推薦模型和最低需求模型？[Gap]

## API 行為變更需求品質（/summarize 端點）

- [ ] CHK024 - 「完全取代」的範圍是否精確定義？（摘要、ActionItem、Topic 都刪，Speaker/Utterance 保留）[Clarity, Spec §FR-009]
- [ ] CHK025 - 重新生成過程中如果 Ollama 失敗，舊資料是否已被刪除的回滾需求是否定義？[Edge Case, Gap]
- [ ] CHK026 - 重新生成摘要時的進度回報需求是否定義？（像新上傳一樣有進度條？）[Gap]
- [ ] CHK027 - 並行請求同一會議的 `/summarize` 是否需要防護？（重複刪除/寫入）[Coverage, Gap]
- [ ] CHK028 - 重新生成後的 `semantic_analysis` 儲存需求是否與首次生成一致？[Consistency]
- [ ] CHK029 - `/summarize` 端點的 HTTP 回應是否反映 GPU/CPU fallback 資訊？[Gap]
- [ ] CHK030 - 摘要生成中使用者意外關閉瀏覽器時的行為需求是否定義？[Edge Case, Gap]

## 效能與超時需求品質

- [ ] CHK031 - SC-001「1 分鐘以內」的量測條件是否明確？（逐字稿長度、模型大小、GPU 型號）[Measurability, Spec §SC-001]
- [ ] CHK032 - SC-005「3 倍加速」的基準線是否定義？（預設執行緒數 vs 16 執行緒）[Measurability, Spec §SC-005]
- [ ] CHK033 - 600 秒 timeout 的選擇依據是否記錄？是否有需求定義何時該調整？[Clarity, Spec §FR-007]
- [ ] CHK034 - 長逐字稿截斷後的摘要品質需求是否定義？（截斷 50% 內容後摘要是否仍有價值？）[Gap]
- [ ] CHK035 - CPU 模式和 GPU 模式的效能目標是否分別定義？[Coverage, Gap]

## 可觀測性與日誌需求品質

- [ ] CHK036 - GPU/CPU 模式切換事件是否有結構化日誌需求？[Gap]
- [ ] CHK037 - Ollama 摘要的耗時量測是否有日誌需求？（方便追蹤 GPU vs CPU 效能差異）[Gap]
- [ ] CHK038 - auto fallback 發生時是否需要告警或通知機制？（不只寫日誌）[Gap]
- [ ] CHK039 - VRAM 使用量是否需要在系統狀態 API 中呈現？[Gap]

## 邊界情況與失敗處理需求品質

- [ ] CHK040 - Ollama 服務在摘要生成中途崩潰時的需求是否定義？[Edge Case, Gap]
- [ ] CHK041 - GPU 驅動崩潰（CUDA error）時系統恢復的需求是否定義？[Edge Case, Gap]
- [ ] CHK042 - 逐字稿為空字串但不為 null 時 `/summarize` 的行為是否定義？[Edge Case, Gap]
- [ ] CHK043 - Ollama 回傳不完整 JSON（如被截斷）時的重試或錯誤處理需求是否定義？[Edge Case]
- [ ] CHK044 - 同時有 Whisper 轉錄和手動 `/summarize` 請求競爭 GPU 時的優先順序需求是否定義？[Coverage, Gap]

## 相依性與假設驗證

- [ ] CHK045 - 「Whisper medium 佔用 4.5GB，gemma2 9B 佔用 5GB」的假設是否有驗證依據？[Assumption, Spec §Assumptions]
- [ ] CHK046 - 「釋放 VRAM 後足以載入 Ollama 模型」是否考慮 CUDA context 佔用和碎片化？[Assumption]
- [ ] CHK047 - Ollama REST API 的 `num_gpu` 參數行為是否引用官方文件？[Dependency]
- [ ] CHK048 - PyTorch `torch.cuda.empty_cache()` 是否保證完全釋放 VRAM 的假設是否正確？[Assumption]

## Notes

- Check items off as completed: `[x]`
- 項目引用 `[Spec §X]` 表示對應 spec.md 中的特定章節
- 項目標記 `[Gap]` 表示需求中可能缺少的面向
- 項目標記 `[Assumption]` 表示需要驗證的假設
